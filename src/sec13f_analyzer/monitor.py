"""
13F 监控服务

定期检查投资组合的 13F 报告更新并发送通知
"""

import json
import signal
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from .analyzer import SEC13FAnalyzer
from .models import HoldingsChange
from .monitor_config import MonitorConfig, PortfolioConfig
from .notifier import (
    FeishuWebhookNotifier,
    NotificationBuilder,
    NotificationMessage,
    WebhookNotifier,
)


class MonitorState:
    """监控状态管理"""

    def __init__(self, state_file: str):
        """
        初始化状态管理器

        Args:
            state_file: 状态文件路径
        """
        self.state_file = Path(state_file)
        self.state: Dict = {}
        self._load_state()

    def _load_state(self):
        """从文件加载状态"""
        if self.state_file.exists():
            try:
                with open(self.state_file) as f:
                    self.state = json.load(f)
                logger.info(f"从 {self.state_file} 加载状态")
            except Exception as e:
                logger.warning(f"加载状态文件失败: {e}，将使用空状态")
                self.state = {}
        else:
            logger.info("状态文件不存在，将创建新状态")
            self.state = {}

    def _save_state(self):
        """保存状态到文件"""
        try:
            with open(self.state_file, "w") as f:
                json.dump(self.state, f, indent=2)
            logger.debug(f"状态已保存到 {self.state_file}")
        except Exception as e:
            logger.error(f"保存状态文件失败: {e}")

    def get_last_check(self, cik: str) -> Optional[datetime]:
        """
        获取上次检查时间

        Args:
            cik: CIK 编号

        Returns:
            datetime: 上次检查时间，如果没有则返回 None
        """
        last_check_str = self.state.get(cik, {}).get("last_check")
        if last_check_str:
            try:
                return datetime.fromisoformat(last_check_str)
            except ValueError:
                return None
        return None

    def get_last_quarter(self, cik: str) -> Optional[str]:
        """
        获取上次检测到的季度

        Args:
            cik: CIK 编号

        Returns:
            str: 季度字符串，如 "2024Q3"
        """
        last_quarter = self.state.get(cik, {}).get("last_quarter")
        return last_quarter if isinstance(last_quarter, str) else None

    def update(self, cik: str, quarter: Optional[str] = None):
        """
        更新状态

        Args:
            cik: CIK 编号
            quarter: 最新的季度
        """
        if cik not in self.state:
            self.state[cik] = {}

        self.state[cik]["last_check"] = datetime.now().isoformat()

        if quarter:
            self.state[cik]["last_quarter"] = quarter

        self._save_state()


class SEC13FMonitor:
    """13F 监控服务"""

    def __init__(self, config: MonitorConfig):
        """
        初始化监控服务

        Args:
            config: 监控配置
        """
        self.config = config
        self.analyzer = SEC13FAnalyzer(config.service.user_agent)
        self.state = MonitorState(config.service.state_file)
        self.notifiers = self._create_notifiers()
        self.running = False

        # 设置信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """信号处理器"""
        logger.info(f"收到信号 {signum}，准备停止服务...")
        self.running = False

    def _create_notifiers(self) -> list[WebhookNotifier]:
        """创建通知器列表"""
        notifiers: list[WebhookNotifier] = []

        for webhook in self.config.enabled_webhooks:
            if webhook.type == "feishu":
                notifier = FeishuWebhookNotifier(webhook.url)
                notifiers.append(notifier)

                # 发送测试消息
                if webhook.send_test_on_start:
                    notifier.send_test_message()

            else:
                logger.warning(f"不支持的 webhook 类型: {webhook.type}")

        return notifiers

    def _send_notification(self, message: NotificationMessage):
        """
        发送通知到所有启用的 webhook

        Args:
            message: 通知消息
        """
        for notifier in self.notifiers:
            try:
                notifier.send(message)
            except Exception as e:
                logger.error(f"发送通知失败: {e}")

    def _check_portfolio(self, portfolio: PortfolioConfig) -> bool:
        """
        检查单个投资组合

        Args:
            portfolio: 投资组合配置

        Returns:
            bool: 是否发现新报告
        """
        try:
            logger.info(f"检查 {portfolio.name} (CIK: {portfolio.cik}) 的 13F 报告...")

            # 获取最近的 13F 报告列表，覆盖至少两年的窗口，
            # 以便定位最新报告对应的上一季度报告。
            filings = self.analyzer.data_fetcher.get_13f_filings(portfolio.cik, years=2)

            if not filings:
                logger.info(f"未找到 {portfolio.name} 的 13F 报告")
                return False

            # 获取最新的报告
            latest_filing = filings[0]
            latest_quarter = latest_filing["quarter"]
            filing_date = latest_filing["filing_date"]

            # 检查是否是新报告
            last_quarter = self.state.get_last_quarter(portfolio.cik)

            if last_quarter == latest_quarter:
                logger.debug(f"{portfolio.name} 没有新报告（最新: {latest_quarter}）")
                self.state.update(portfolio.cik)
                return False

            # 检查报告日期是否足够新
            last_check = self.state.get_last_check(portfolio.cik)
            if last_check:
                days_since_last = (datetime.now() - last_check).days
                if days_since_last < portfolio.min_report_days:
                    logger.debug(
                        f"{portfolio.name} 距上次检查仅 {days_since_last} 天，跳过"
                    )
                    return False

            logger.info(
                f"发现 {portfolio.name} 的新报告: {latest_quarter} "
                f"(申报日期: {filing_date.strftime('%Y-%m-%d')})"
            )

            # 获取持仓详情
            holdings = self.analyzer.get_holdings(portfolio.cik, latest_quarter)

            if not holdings:
                logger.warning(f"无法获取 {portfolio.name} 的持仓数据")
                return False

            # 构建通知
            top_holdings = None
            if self.config.notification.include_holdings_summary:
                max_count = self.config.notification.max_holdings_in_summary
                top_holdings_list = self.analyzer.get_top_holdings(
                    portfolio.cik, latest_quarter, max_count
                )

                if top_holdings_list:
                    top_holdings = []
                    for holding in top_holdings_list:
                        percentage = (holding.market_value / holdings.total_value) * 100
                        top_holdings.append(
                            {
                                "name": holding.issuer_name,
                                "value": holding.market_value,
                                "percentage": percentage,
                            }
                        )

            # 计算与上一季度的持仓变动
            changes_summary: Optional[Dict[str, Any]] = None
            if self.config.notification.include_changes_summary:
                prev_quarter = self._find_previous_quarter(filings, latest_quarter)
                if prev_quarter:
                    changes_summary = self._build_changes_summary(
                        portfolio.cik,
                        prev_quarter,
                        latest_quarter,
                        holdings.total_value,
                    )
                else:
                    logger.info(
                        f"{portfolio.name} 未找到上一季度报告，跳过持仓变动摘要"
                    )

            # 报告链接
            report_url = None
            if self.config.notification.include_report_link:
                report_url = (
                    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
                    f"&CIK={portfolio.cik}&type=13F&dateb=&owner=exclude&count=10"
                )

            message = NotificationBuilder.build_new_filing_notification(
                fund_name=portfolio.name,
                cik=portfolio.cik,
                quarter=latest_quarter,
                filing_date=filing_date,
                total_value=holdings.total_value,
                holdings_count=len(holdings.holdings),
                top_holdings=top_holdings,
                report_url=report_url,
                changes_summary=changes_summary,
            )

            # 发送通知
            self._send_notification(message)

            # 更新状态
            self.state.update(portfolio.cik, latest_quarter)

            return True

        except Exception as e:
            logger.error(f"检查 {portfolio.name} 时出错: {e}")
            return False

    @staticmethod
    def _find_previous_quarter(
        filings: List[Dict[str, Any]], latest_quarter: str
    ) -> Optional[str]:
        """
        从报告列表中定位最新季度之前的一个季度。

        ``filings`` 按申报日期降序排列，可能因为修订（13F-HR/A）而出现
        重复季度，因此需要找到与 ``latest_quarter`` 不同且较早的季度。

        Args:
            filings: ``get_13f_filings`` 返回的报告列表
            latest_quarter: 最新报告所属季度

        Returns:
            上一个季度字符串，找不到时返回 ``None``。
        """
        for filing in filings:
            quarter = filing.get("quarter")
            if quarter and quarter != latest_quarter:
                return str(quarter)
        return None

    def _build_changes_summary(
        self,
        cik: str,
        prev_quarter: str,
        curr_quarter: str,
        total_curr_value: float,
    ) -> Optional[Dict[str, Any]]:
        """
        构建用于通知的持仓变动摘要数据。

        Args:
            cik: 基金 CIK
            prev_quarter: 上一季度
            curr_quarter: 最新季度
            total_curr_value: 当前总持仓市值，用于计算占比

        Returns:
            摘要字典，无法计算时返回 ``None``。
        """
        try:
            changes = self.analyzer.analyze_holdings_changes(
                cik, prev_quarter, curr_quarter
            )
        except Exception as e:  # pragma: no cover - 防御性日志
            logger.warning(f"计算 {cik} 持仓变动失败: {e}")
            return None

        if changes is None:
            return None

        return self._serialize_changes_summary(changes, total_curr_value)

    def _serialize_changes_summary(
        self, changes: HoldingsChange, total_curr_value: float
    ) -> Dict[str, Any]:
        """将 ``HoldingsChange`` 转换为通知所需的紧凑字典。"""
        max_items = max(0, self.config.notification.max_changes_in_summary)

        new_items = sorted(
            changes.new_positions,
            key=lambda c: c.curr_value or 0.0,
            reverse=True,
        )[:max_items]
        closed_items = sorted(
            changes.closed_positions,
            key=lambda c: c.prev_value or 0.0,
            reverse=True,
        )[:max_items]
        increased_items = sorted(
            changes.increased_positions,
            key=lambda c: c.value_change or 0.0,
            reverse=True,
        )[:max_items]
        decreased_items = sorted(
            changes.decreased_positions,
            key=lambda c: c.value_change or 0.0,
        )[:max_items]

        def _percentage(value: Optional[float]) -> float:
            if not value or total_curr_value <= 0:
                return 0.0
            return (value / total_curr_value) * 100

        return {
            "from_quarter": changes.from_quarter,
            "to_quarter": changes.to_quarter,
            "total_prev_value": changes.total_prev_value,
            "total_curr_value": changes.total_curr_value,
            "total_value_change": changes.total_value_change,
            "total_percentage_change": changes.total_percentage_change,
            "counts": {
                "new": len(changes.new_positions),
                "closed": len(changes.closed_positions),
                "increased": len(changes.increased_positions),
                "decreased": len(changes.decreased_positions),
            },
            "new": [
                {
                    "name": c.issuer_name,
                    "value": c.curr_value or 0.0,
                    "percentage": _percentage(c.curr_value),
                }
                for c in new_items
            ],
            "closed": [
                {
                    "name": c.issuer_name,
                    "prev_value": c.prev_value or 0.0,
                }
                for c in closed_items
            ],
            "increased": [
                {
                    "name": c.issuer_name,
                    "prev_value": c.prev_value or 0.0,
                    "curr_value": c.curr_value or 0.0,
                    "value_change": c.value_change or 0.0,
                    "percentage_change": c.percentage_change or 0.0,
                }
                for c in increased_items
            ],
            "decreased": [
                {
                    "name": c.issuer_name,
                    "prev_value": c.prev_value or 0.0,
                    "curr_value": c.curr_value or 0.0,
                    "value_change": c.value_change or 0.0,
                    "percentage_change": c.percentage_change or 0.0,
                }
                for c in decreased_items
            ],
        }

    def check_once(self) -> int:
        """
        执行一次检查

        Returns:
            int: 发现的新报告数量
        """
        logger.info("开始检查所有投资组合...")

        new_reports_count = 0

        for portfolio in self.config.enabled_portfolios:
            if self._check_portfolio(portfolio):
                new_reports_count += 1

            # 避免请求过快
            time.sleep(1)

        logger.info(f"检查完成，发现 {new_reports_count} 个新报告")
        return new_reports_count

    def start(self):
        """启动监控服务"""
        logger.info("=" * 60)
        logger.info("13F 监控服务启动")
        logger.info("=" * 60)
        logger.info(f"监控的投资组合数量: {len(self.config.enabled_portfolios)}")
        logger.info(f"检查间隔: {self.config.service.check_interval} 分钟")
        logger.info(f"状态文件: {self.config.service.state_file}")

        for portfolio in self.config.enabled_portfolios:
            logger.info(f"  - {portfolio.name} (CIK: {portfolio.cik})")

        logger.info("=" * 60)

        # 发送启动通知
        start_message = NotificationBuilder.build_service_start_notification(
            portfolios_count=len(self.config.enabled_portfolios),
            check_interval=self.config.service.check_interval,
        )
        self._send_notification(start_message)

        self.running = True

        try:
            # 首次检查
            self.check_once()

            # 持续监控
            while self.running:
                next_check = datetime.now() + timedelta(
                    minutes=self.config.service.check_interval
                )
                logger.info(f"下次检查时间: {next_check.strftime('%Y-%m-%d %H:%M:%S')}")

                # 等待下次检查
                sleep_seconds = self.config.service.check_interval * 60
                for _ in range(sleep_seconds):
                    if not self.running:
                        break
                    time.sleep(1)

                if self.running:
                    self.check_once()

        except KeyboardInterrupt:
            logger.info("收到中断信号")
        except Exception as e:
            logger.error(f"监控服务出错: {e}")
            error_message = NotificationBuilder.build_error_notification(str(e))
            self._send_notification(error_message)
        finally:
            logger.info("13F 监控服务已停止")

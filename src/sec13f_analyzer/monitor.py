"""
13F 监控服务

定期检查投资组合的 13F 报告更新并发送通知
"""

import json
import signal
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

from loguru import logger

from .analyzer import SEC13FAnalyzer
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

            # 获取最近的 13F 报告列表
            filings = self.analyzer.data_fetcher.get_13f_filings(portfolio.cik, years=1)

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
                f"发现 {portfolio.name} 的新报告: {latest_quarter} (申报日期: {filing_date.strftime('%Y-%m-%d')})"
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

            # 报告链接
            report_url = None
            if self.config.notification.include_report_link:
                report_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={portfolio.cik}&type=13F&dateb=&owner=exclude&count=10"

            message = NotificationBuilder.build_new_filing_notification(
                fund_name=portfolio.name,
                cik=portfolio.cik,
                quarter=latest_quarter,
                filing_date=filing_date,
                total_value=holdings.total_value,
                holdings_count=len(holdings.holdings),
                top_holdings=top_holdings,
                report_url=report_url,
            )

            # 发送通知
            self._send_notification(message)

            # 更新状态
            self.state.update(portfolio.cik, latest_quarter)

            return True

        except Exception as e:
            logger.error(f"检查 {portfolio.name} 时出错: {e}")
            return False

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

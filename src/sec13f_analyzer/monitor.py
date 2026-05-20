"""
13F 监控服务

定期检查投资组合的 13F 报告更新并发送通知
"""

import json
import signal
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

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
    """监控状态管理。

    状态文件按 CIK 维度组织，结构示例::

        {
            "0001067983": {
                "last_check": "2025-05-20T12:00:00",
                "last_quarter": "2024Q4",
                "seen_accessions": [
                    "0000950123-25-001234",
                    "0000950123-25-005678"
                ]
            }
        }

    - ``last_check``: 上一次 ``_check_portfolio`` 的时间（人读用）
    - ``last_quarter``: 最近一次成功通知所对应的 ``report_quarter``
      （仅用作旧逻辑兼容与迁移 cutoff，不再参与判新）
    - ``seen_accessions``: 已经处理过的 accession 列表（去重 + 通知判新
      的唯一稳定 key；同一 accession 永不重复通知）
    """

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

    def has_cik(self, cik: str) -> bool:
        """该 CIK 是否在状态文件中已有任何记录（含历史）。"""
        return cik in self.state

    def get_seen_accessions(self, cik: str) -> List[str]:
        """获取该 CIK 已处理过的 accession 列表。"""
        if cik not in self.state:
            return []
        seen = self.state[cik].get("seen_accessions", [])
        return list(seen) if isinstance(seen, list) else []

    def mark_accessions_seen(self, cik: str, accessions: Iterable[str]) -> None:
        """把若干 accession 标记为已处理，去重后写回状态文件。

        Args:
            cik: CIK 编号
            accessions: 待标记的 accession 集合（``None`` 项会被忽略）
        """
        new_items = [a for a in accessions if a]
        if not new_items:
            return

        if cik not in self.state:
            self.state[cik] = {}
        existing: List[str] = self.state[cik].get("seen_accessions", []) or []
        if not isinstance(existing, list):
            existing = []
        merged: List[str] = list(existing)
        existing_set: Set[str] = set(existing)
        for acc in new_items:
            if acc not in existing_set:
                merged.append(acc)
                existing_set.add(acc)
        self.state[cik]["seen_accessions"] = merged
        self._save_state()

    def has_seen_accessions(self, cik: str) -> bool:
        """该 CIK 的状态中是否已经存在 ``seen_accessions`` 键。

        用于区分"全新 CIK"、"刚从旧 schema 迁移"和"正常增量"。
        """
        if cik not in self.state:
            return False
        return "seen_accessions" in self.state[cik]


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

    def _send_notification(self, message: NotificationMessage) -> bool:
        """
        发送通知到所有启用的 webhook

        Args:
            message: 通知消息

        Returns:
            bool: 至少有一个 notifier 成功发送时为 ``True``；全部失败
            （或没有任何 notifier）时为 ``False``。调用方可据此判断是否
            应该把 filing 标记为已处理——失败时不应标记，避免漏推。
        """
        if not self.notifiers:
            logger.warning("没有可用的 webhook 通知器，跳过发送")
            return False

        any_success = False
        for notifier in self.notifiers:
            try:
                notifier.send(message)
                any_success = True
            except Exception as e:
                logger.error(f"发送通知失败: {e}")
        return any_success

    def _resolve_filing_quarter(self, filing: Dict[str, Any]) -> str:
        """返回 filing 应归属的报告期季度字符串。

        优先使用 fetcher 在 ``resolve_period_of_report=True`` 下填入的
        ``report_quarter``（基于真实 ``periodOfReport``），缺失时回退到
        基于 ``filing_date`` 的近似值。
        """
        rq = filing.get("report_quarter")
        if isinstance(rq, str) and rq:
            return rq
        return str(filing["quarter"])

    def _migrate_legacy_state(self, cik: str, filings: List[Dict[str, Any]]) -> None:
        """对旧版本写入的状态做一次性迁移。

        旧实现只记录 ``last_quarter``，不区分单份 accession。升级到新
        逻辑后，第一次轮询时把 ``report_quarter <= last_quarter`` 的所
        有 accession 直接标记已见，避免在升级瞬间把过去 2 年的报告全
        部当成"新"再推一遍。

        **取舍**：这同时意味着之前被旧 bug 吞掉的 HR/A 修订不会被回溯
        补推。这是有意的——避免升级时一次性灌水更重要。

        Args:
            cik: CIK 编号
            filings: 当前 EDGAR 上的报告列表（已含 accession_number）
        """
        if self.state.has_seen_accessions(cik):
            return

        last_quarter = self.state.get_last_quarter(cik)
        if not last_quarter:
            return

        migrate_accessions: List[str] = []
        for filing in filings:
            accession = filing.get("accession_number")
            if not accession:
                continue
            if self._resolve_filing_quarter(filing) <= last_quarter:
                migrate_accessions.append(accession)

        if migrate_accessions:
            logger.info(
                f"CIK {cik} 旧状态迁移：将 {len(migrate_accessions)} 份"
                f" report_quarter ≤ {last_quarter} 的 accession 标记已见"
            )
            self.state.mark_accessions_seen(cik, migrate_accessions)
        else:
            # 即便没有要迁移的条目，也写一个空 list 表明已完成迁移，
            # 防止下一轮再次走 legacy 分支。
            self.state.mark_accessions_seen(cik, [])
            if cik in self.state.state:
                self.state.state[cik].setdefault("seen_accessions", [])
                self.state._save_state()

    def _gate_first_run(self, cik: str, filings: List[Dict[str, Any]]) -> None:
        """全新 CIK 首次轮询时，只保留最新一份 filing 作为可推送对象。

        把列表里除最新一份外的所有 accession 直接标记为 seen，避免在
        首次启动时一次性把过去 2 年的报告都推到 webhook。

        Args:
            cik: CIK 编号
            filings: 已按 ``filing_date`` 降序排列的 filing 列表
        """
        if self.state.has_cik(cik):
            return
        if len(filings) <= 1:
            # 只有 0 或 1 份 filing，没有需要"压制"的历史项
            self.state.mark_accessions_seen(cik, [])
            return

        # 跳过 filings[0]（最新一份），其余全部标记 seen
        skipped: List[str] = [
            f["accession_number"] for f in filings[1:] if f.get("accession_number")
        ]
        if skipped:
            logger.info(
                f"CIK {cik} 首次启动：跳过历史 {len(skipped)} 份 filing，"
                "仅对最新一份发送通知"
            )
            self.state.mark_accessions_seen(cik, skipped)
        else:
            self.state.mark_accessions_seen(cik, [])

    def _check_portfolio(self, portfolio: PortfolioConfig) -> bool:
        """
        检查单个投资组合

        新流程（按 accession 幂等去重）：

        1. 取最近若干年 13F filings（带 ``accession_number`` 与
           ``report_quarter``）。
        2. 对全新 CIK 做"首跑门控"，对旧 schema 状态做一次性迁移。
        3. 找出未见 accession，按 ``report_quarter`` 分组——同一报告期
           即便包含原始 HR + 多个 HR/A，也只发一条通知，但通知会标记
           "修订"且通过 ``use_cache=False`` 强制取最新合并后的持仓。
        4. 每个季度组发送通知；只有发送成功才把组内 accession 标记
           seen，避免 webhook 故障时永久丢失通知。

        Args:
            portfolio: 投资组合配置

        Returns:
            bool: 是否实际发送了至少一条新通知。
        """
        try:
            logger.info(f"检查 {portfolio.name} (CIK: {portfolio.cik}) 的 13F 报告...")

            filings = self.analyzer.data_fetcher.get_13f_filings(
                portfolio.cik, years=2, resolve_period_of_report=True
            )

            if not filings:
                logger.info(f"未找到 {portfolio.name} 的 13F 报告")
                self.state.update(portfolio.cik)
                return False

            # filings 由 fetcher 按 filing_date 降序排列
            self._migrate_legacy_state(portfolio.cik, filings)
            self._gate_first_run(portfolio.cik, filings)

            seen = set(self.state.get_seen_accessions(portfolio.cik))
            unseen = [
                f
                for f in filings
                if f.get("accession_number") and f["accession_number"] not in seen
            ]

            if not unseen:
                logger.debug(f"{portfolio.name} 没有新 filing")
                self.state.update(portfolio.cik)
                return False

            # 按 report_quarter 分组；同一季度合并成一条通知
            grouped: Dict[str, List[Dict[str, Any]]] = {}
            for f in unseen:
                q = self._resolve_filing_quarter(f)
                grouped.setdefault(q, []).append(f)

            any_notified = False
            latest_quarter_notified: Optional[str] = None

            # 季度从新到旧依次处理；同季度内按 filing_date 升序
            for quarter in sorted(grouped.keys(), reverse=True):
                group = sorted(grouped[quarter], key=lambda x: x["filing_date"])
                notified = self._notify_for_quarter(
                    portfolio=portfolio,
                    quarter=quarter,
                    group_filings=group,
                    all_filings=filings,
                )
                if notified:
                    any_notified = True
                    if (
                        latest_quarter_notified is None
                        or quarter > latest_quarter_notified
                    ):
                        latest_quarter_notified = quarter

            self.state.update(portfolio.cik, latest_quarter_notified)
            return any_notified

        except Exception as e:
            logger.error(f"检查 {portfolio.name} 时出错: {e}")
            return False

    def _notify_for_quarter(
        self,
        portfolio: PortfolioConfig,
        quarter: str,
        group_filings: List[Dict[str, Any]],
        all_filings: List[Dict[str, Any]],
    ) -> bool:
        """对单个季度的一组未见 filing 发送一次通知。

        Args:
            portfolio: 投资组合配置
            quarter: ``report_quarter``（``YYYYQN``）
            group_filings: 本次需要处理的同季度未见 filing 集合
            all_filings: 当前轮询拉到的全量 filings（用于推算上一季度）

        Returns:
            bool: 是否成功发送（任一 webhook 返回成功）。成功时 group
            内所有 accession 会被标记 seen。
        """
        # 判定本次通知是"新报告"还是"修订报告"——只要本季度此前已经
        # 推送过任何 accession，或本批 filings 中含修订件，就视为修订。
        seen = set(self.state.get_seen_accessions(portfolio.cik))
        prior_for_quarter = any(
            f.get("accession_number") in seen
            and self._resolve_filing_quarter(f) == quarter
            for f in all_filings
        )
        in_group_amendment = any(f.get("is_amendment") for f in group_filings)
        is_amendment_notification = prior_for_quarter or in_group_amendment

        # 取最新一份作为通知主体的 filing_date 来源
        latest_in_group = max(group_filings, key=lambda f: f["filing_date"])
        filing_date = latest_in_group["filing_date"]

        logger.info(
            f"发现 {portfolio.name} 的{'修订' if is_amendment_notification else '新'}"
            f"报告: {quarter}（{len(group_filings)} 份 filing，最新提交日 "
            f"{filing_date.strftime('%Y-%m-%d')}）"
        )

        # 强制不走缓存，确保修订件能拿到最新合并状态
        holdings = self.analyzer.get_holdings(portfolio.cik, quarter, use_cache=False)
        if not holdings:
            logger.warning(f"无法获取 {portfolio.name} {quarter} 的持仓数据")
            return False

        top_holdings = None
        if self.config.notification.include_holdings_summary:
            max_count = self.config.notification.max_holdings_in_summary
            top_holdings_list = self.analyzer.get_top_holdings(
                portfolio.cik, quarter, max_count
            )
            if top_holdings_list:
                top_holdings = []
                for holding in top_holdings_list:
                    percentage = (
                        (holding.market_value / holdings.total_value) * 100
                        if holdings.total_value
                        else 0.0
                    )
                    top_holdings.append(
                        {
                            "name": holding.issuer_name,
                            "security_class": holding.security_class,
                            "value": holding.market_value,
                            "percentage": percentage,
                        }
                    )

        changes_summary: Optional[Dict[str, Any]] = None
        if self.config.notification.include_changes_summary:
            prev_quarter = self._find_previous_quarter(all_filings, quarter)
            if prev_quarter:
                changes_summary = self._build_changes_summary(
                    portfolio.cik,
                    prev_quarter,
                    quarter,
                    holdings.total_value,
                )
            else:
                logger.info(f"{portfolio.name} 未找到上一季度报告，跳过持仓变动摘要")

        report_url = None
        if self.config.notification.include_report_link:
            report_url = (
                "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
                f"&CIK={portfolio.cik}&type=13F&dateb=&owner=exclude&count=10"
            )

        amendment_types: Optional[List[str]] = None
        amendment_numbers: Optional[List[int]] = None
        if is_amendment_notification:
            # 收集本批 filings 中含有的修订元信息（amendment_info 由
            # data_fetcher.get_holdings_data 在解析时填入 holdings）
            amendment_types = []
            amendment_numbers = []
            for meta in holdings.amendment_metadata or []:
                if meta.amendment_type is not None:
                    amendment_types.append(meta.amendment_type.value)
                if meta.amendment_number is not None:
                    amendment_numbers.append(meta.amendment_number)
            amendment_types = amendment_types or None
            amendment_numbers = amendment_numbers or None

        message = NotificationBuilder.build_new_filing_notification(
            fund_name=portfolio.name,
            cik=portfolio.cik,
            quarter=quarter,
            filing_date=filing_date,
            total_value=holdings.total_value,
            holdings_count=len(holdings.holdings),
            top_holdings=top_holdings,
            report_url=report_url,
            changes_summary=changes_summary,
            period_end_date=holdings.period_end_date,
            is_amendment=is_amendment_notification,
            amendment_types=amendment_types,
            amendment_numbers=amendment_numbers,
        )

        success = self._send_notification(message)
        if success:
            self.state.mark_accessions_seen(
                portfolio.cik,
                [
                    f["accession_number"]
                    for f in group_filings
                    if f.get("accession_number")
                ],
            )
        else:
            logger.warning(
                f"{portfolio.name} {quarter} 通知全部 webhook 失败，"
                "保留未见标记，下一轮重试"
            )
        return success

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
                    "security_class": c.security_class,
                    "value": c.curr_value or 0.0,
                    "percentage": _percentage(c.curr_value),
                }
                for c in new_items
            ],
            "closed": [
                {
                    "name": c.issuer_name,
                    "security_class": c.security_class,
                    "prev_value": c.prev_value or 0.0,
                }
                for c in closed_items
            ],
            "increased": [
                {
                    "name": c.issuer_name,
                    "security_class": c.security_class,
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
                    "security_class": c.security_class,
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

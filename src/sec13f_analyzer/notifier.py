"""
Webhook 通知模块

实现飞书等平台的 webhook 消息推送
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from loguru import logger

# 飞书 lark_md 支持的颜色名称
_FEISHU_COLOR_RED = "red"
_FEISHU_COLOR_GREEN = "green"
_FEISHU_COLOR_GREY = "grey"

# 中文星期标签，用于在通知中明确申报日期星期，降低看错日期的风险。
_WEEKDAY_LABELS_ZH = ("一", "二", "三", "四", "五", "六", "日")


def _format_filing_date(filing_date: datetime) -> str:
    """格式化申报日期：``2024-11-14（周四）``。"""
    weekday = _WEEKDAY_LABELS_ZH[filing_date.weekday()]
    return f"{filing_date.strftime('%Y-%m-%d')}（周{weekday}）"


def _quarter_end_date(quarter: str) -> Optional[str]:
    """根据 ``YYYYQN`` 推断报告期截止日期（自然季度末）。"""
    if not quarter or "Q" not in quarter:
        return None
    try:
        year_str, q_str = quarter.split("Q", 1)
        year = int(year_str)
        q = int(q_str)
    except (ValueError, AttributeError):
        return None
    quarter_ends = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}
    if q not in quarter_ends:
        return None
    return f"{year}-{quarter_ends[q]}"


def _wrap_color(text: str, color: str) -> str:
    """用 ``<font color='...'>`` 包裹文本以在飞书卡片中高亮显示。"""
    return f"<font color='{color}'>{text}</font>"


def _escape_table_cell(value: str) -> str:
    """转义 markdown 表格单元格中的特殊字符。"""
    return value.replace("|", "\\|").replace("\n", " ")


@dataclass
class NotificationMessage:
    """通知消息"""

    title: str
    content: str
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class WebhookNotifier:
    """Webhook 通知器基类"""

    def __init__(self, webhook_url: str, timeout: int = 10):
        """
        初始化通知器

        Args:
            webhook_url: Webhook URL
            timeout: 请求超时时间（秒）
        """
        self.webhook_url = webhook_url
        self.timeout = timeout

    def send(self, message: NotificationMessage) -> bool:
        """
        发送通知消息

        Args:
            message: 通知消息

        Returns:
            bool: 是否发送成功
        """
        raise NotImplementedError("子类必须实现 send 方法")


class FeishuWebhookNotifier(WebhookNotifier):
    """飞书 Webhook 通知器"""

    def send(self, message: NotificationMessage) -> bool:
        """
        发送飞书通知

        Args:
            message: 通知消息

        Returns:
            bool: 是否发送成功
        """
        try:
            payload = self._build_payload(message)

            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout,
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 0:
                    logger.info(f"飞书消息发送成功: {message.title}")
                    return True
                else:
                    logger.error(f"飞书消息发送失败: {result.get('msg')}")
                    return False
            else:
                logger.error(f"飞书 webhook 请求失败: HTTP {response.status_code}")
                return False

        except requests.RequestException as e:
            logger.error(f"发送飞书消息时出错: {e}")
            return False
        except Exception as e:
            logger.error(f"构建飞书消息时出错: {e}")
            return False

    def _build_payload(self, message: NotificationMessage) -> Dict[str, Any]:
        """
        构建飞书消息负载

        使用飞书交互式卡片（``msg_type: interactive``）以便支持表格、
        颜色高亮等富文本能力；卡片正文为单个 ``div`` 元素，文本类型
        为 ``lark_md``，可直接渲染标准 Markdown。

        Args:
            message: 通知消息

        Returns:
            dict: 飞书卡片消息 JSON
        """
        title = message.title or " "
        # lark_md 内容为空时，飞书会拒绝渲染，回退到一个占位符。
        content = (message.content or "").strip() or " "

        return {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": "blue",
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": content,
                        },
                    }
                ],
            },
        }

    def send_test_message(self) -> bool:
        """
        发送测试消息

        Returns:
            bool: 是否发送成功
        """
        test_message = NotificationMessage(
            title="13F 监控服务测试",
            content="**监控服务已启动**\n\n服务将定期检查配置的投资组合的 13F 报告更新。",
        )
        return self.send(test_message)


class NotificationBuilder:
    """通知消息构建器"""

    @staticmethod
    def _format_security_label(name: str, security_class: Optional[str]) -> str:
        """将证券类别追加到展示名称中。"""
        if security_class:
            return f"{name} ({security_class})"
        return name

    @staticmethod
    def build_new_filing_notification(
        fund_name: str,
        cik: str,
        quarter: str,
        filing_date: datetime,
        total_value: float,
        holdings_count: int,
        top_holdings: Optional[List[Dict]] = None,
        report_url: Optional[str] = None,
        changes_summary: Optional[Dict[str, Any]] = None,
        period_end_date: Optional[datetime] = None,
    ) -> NotificationMessage:
        """
        构建新 13F 报告通知

        Args:
            fund_name: 基金名称
            cik: CIK 编号
            quarter: 季度
            filing_date: 申报日期（提交至 SEC 的日期）
            total_value: 总持仓价值
            holdings_count: 持仓数量
            top_holdings: 前几大持仓
            report_url: 报告链接
            changes_summary: 与上一季度的持仓变动摘要，结构示例::

                {
                    "from_quarter": "2024Q2",
                    "to_quarter": "2024Q3",
                    "total_prev_value": 2_900_000_000.0,
                    "total_curr_value": 3_000_000_000.0,
                    "total_value_change": 100_000_000.0,
                    "total_percentage_change": 3.45,
                    "counts": {
                        "new": 5, "closed": 3, "increased": 10, "decreased": 8,
                    },
                    "new": [
                        {"name": "Apple Inc.", "value": 1_000_000.0,
                         "percentage": 0.1},
                        ...
                    ],
                    "closed": [
                        {"name": "Tesla Inc", "prev_value": 500_000.0},
                        ...
                    ],
                    "increased": [
                        {"name": "Microsoft Corp.", "prev_value": 1.0,
                         "curr_value": 2.0, "value_change": 1.0,
                         "percentage_change": 100.0},
                        ...
                    ],
                    "decreased": [
                        {"name": "Apple Inc.", "prev_value": 2.0,
                         "curr_value": 1.0, "value_change": -1.0,
                         "percentage_change": -50.0},
                        ...
                    ],
                }
            period_end_date: 报告期截止日期（持仓 as-of 日期）。若未提供，
                将根据 ``quarter`` 推断自然季度末。该参数与 ``filing_date``
                一同明确呈现，避免阅读者混淆两个日期。

        Returns:
            NotificationMessage: 通知消息
        """
        title = f"📊 {fund_name} 发布了新的 13F 报告"

        # 优先使用真实的报告期截止日；否则按自然季度末推断。
        period_end_str: Optional[str]
        if period_end_date is not None:
            period_end_str = period_end_date.strftime("%Y-%m-%d")
        else:
            period_end_str = _quarter_end_date(quarter)

        period_line = f"📅 **报告期**: `{quarter}`"
        if period_end_str:
            period_line += f"（持仓截至 {period_end_str}）"

        filing_line = "🔴 **申报日期**: " + _wrap_color(
            f"**{_format_filing_date(filing_date)}**", _FEISHU_COLOR_RED
        )

        content_parts = [
            f"**基金**: {fund_name}",
            f"**CIK**: `{cik}`",
            period_line,
            filing_line,
            f"💼 **总持仓价值**: ${total_value:,.0f}",
            f"📊 **持仓股票数**: {holdings_count}",
        ]

        if top_holdings:
            content_parts.append("")
            content_parts.append("**当前主要持仓**")
            content_parts.extend(
                NotificationBuilder._build_holdings_table(top_holdings)
            )

        if changes_summary:
            content_parts.extend(
                NotificationBuilder._format_changes_summary(changes_summary)
            )

        if report_url:
            content_parts.append("")
            content_parts.append(f"[查看完整报告]({report_url})")

        content = "\n".join(content_parts)

        return NotificationMessage(title=title, content=content)

    @staticmethod
    def _build_holdings_table(items: List[Dict]) -> List[str]:
        """渲染 ``当前主要持仓`` / ``新增持仓`` 的 markdown 表格。"""
        rows: List[str] = [
            "| # | 证券 | 市值 (USD) | 占比 |",
            "| --- | --- | --- | --- |",
        ]
        for i, item in enumerate(items, 1):
            name = _escape_table_cell(
                NotificationBuilder._format_security_label(
                    item.get("name", ""), item.get("security_class")
                )
            )
            value = item.get("value", 0) or 0
            percentage = item.get("percentage", 0) or 0
            rows.append(f"| {i} | {name} | ${value:,.0f} | {percentage:.2f}% |")
        return rows

    @staticmethod
    def _format_changes_summary(changes_summary: Dict[str, Any]) -> List[str]:
        """将持仓变动摘要格式化为消息行（含 markdown 表格）。"""
        from_quarter = changes_summary.get("from_quarter", "")
        to_quarter = changes_summary.get("to_quarter", "")
        counts = changes_summary.get("counts", {}) or {}

        header = "\n**相对上一季度的持仓变动**"
        if from_quarter and to_quarter:
            header += f" ({from_quarter} → {to_quarter})"
        header += ":"

        lines: List[str] = [header]

        total_value_change = changes_summary.get("total_value_change")
        total_percentage_change = changes_summary.get("total_percentage_change")
        if total_value_change is not None and total_percentage_change is not None:
            sign = "+" if total_value_change >= 0 else "-"
            change_text = (
                f"{sign}${abs(total_value_change):,.0f} "
                f"({total_percentage_change:+.2f}%)"
            )
            color = (
                _FEISHU_COLOR_GREEN
                if total_value_change > 0
                else _FEISHU_COLOR_RED if total_value_change < 0 else _FEISHU_COLOR_GREY
            )
            lines.append("**总市值变化**: " + _wrap_color(change_text, color))

        lines.append(
            "**变动概览**: "
            f"新增 {counts.get('new', 0)} / "
            f"清仓 {counts.get('closed', 0)} / "
            f"增持 {counts.get('increased', 0)} / "
            f"减持 {counts.get('decreased', 0)}"
        )

        new_items = changes_summary.get("new") or []
        if new_items:
            lines.append("")
            lines.append("**🆕 新增持仓**")
            lines.extend(NotificationBuilder._build_holdings_table(new_items))

        closed_items = changes_summary.get("closed") or []
        if closed_items:
            lines.append("")
            lines.append("**🚫 清仓持仓**")
            lines.append("| # | 证券 | 前期市值 (USD) |")
            lines.append("| --- | --- | --- |")
            for i, item in enumerate(closed_items, 1):
                name = _escape_table_cell(
                    NotificationBuilder._format_security_label(
                        item.get("name", ""), item.get("security_class")
                    )
                )
                prev_value = item.get("prev_value", 0) or 0
                lines.append(f"| {i} | {name} | ${prev_value:,.0f} |")

        increased_items = changes_summary.get("increased") or []
        if increased_items:
            lines.append("")
            lines.append("**📈 增持持仓**")
            lines.extend(
                NotificationBuilder._build_change_table(
                    increased_items, _FEISHU_COLOR_GREEN
                )
            )

        decreased_items = changes_summary.get("decreased") or []
        if decreased_items:
            lines.append("")
            lines.append("**📉 减持持仓**")
            lines.extend(
                NotificationBuilder._build_change_table(
                    decreased_items, _FEISHU_COLOR_RED
                )
            )

        return lines

    @staticmethod
    def _build_change_table(items: List[Dict], color: str) -> List[str]:
        """渲染 ``增持`` / ``减持`` 表格，市值变化按颜色高亮。"""
        rows: List[str] = [
            "| # | 证券 | 市值变化 (USD) | 占比变化 |",
            "| --- | --- | --- | --- |",
        ]
        for i, item in enumerate(items, 1):
            name = _escape_table_cell(
                NotificationBuilder._format_security_label(
                    item.get("name", ""), item.get("security_class")
                )
            )
            value_change = item.get("value_change", 0) or 0
            percentage_change = item.get("percentage_change", 0) or 0
            sign = "+" if value_change >= 0 else "-"
            value_text = f"{sign}${abs(value_change):,.0f}"
            rows.append(
                f"| {i} | {name} | "
                f"{_wrap_color(value_text, color)} | "
                f"{percentage_change:+.2f}% |"
            )
        return rows

    @staticmethod
    def build_service_start_notification(
        portfolios_count: int, check_interval: int
    ) -> NotificationMessage:
        """
        构建服务启动通知

        Args:
            portfolios_count: 监控的投资组合数量
            check_interval: 检查间隔（分钟）

        Returns:
            NotificationMessage: 通知消息
        """
        title = "✅ 13F 监控服务已启动"

        content = (
            f"**监控中的投资组合**: {portfolios_count} 个\n"
            f"**检查间隔**: {check_interval} 分钟\n\n"
            f"服务将自动检测新的 13F 报告并推送通知。"
        )

        return NotificationMessage(title=title, content=content)

    @staticmethod
    def build_error_notification(error_message: str) -> NotificationMessage:
        """
        构建错误通知

        Args:
            error_message: 错误消息

        Returns:
            NotificationMessage: 通知消息
        """
        title = "❌ 13F 监控服务错误"
        content = f"**错误信息**: {error_message}"

        return NotificationMessage(title=title, content=content)

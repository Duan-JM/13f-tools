"""
Webhook 通知模块

实现飞书等平台的 webhook 消息推送
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from loguru import logger


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

        Args:
            message: 通知消息

        Returns:
            dict: 飞书消息 JSON
        """
        content = self._parse_markdown_to_feishu(message.content)
        # 飞书自定义机器人 post 消息要求 content 至少包含一个段落，
        # 否则会返回 "params error, unknown content value"。
        if not content:
            content = [[{"tag": "text", "text": message.content or " "}]]

        title = message.title or " "

        return {
            "msg_type": "post",
            "content": {
                "post": {
                    "zh_cn": {
                        "title": title,
                        "content": content,
                    }
                }
            },
        }

    def _parse_markdown_to_feishu(self, markdown_text: str) -> List[List[Dict]]:
        """
        将简单的 Markdown 文本转换为飞书富文本格式

        飞书自定义机器人 ``post`` 消息的 ``text`` 标签只接受 ``text`` 与
        ``un_escape`` 字段，不支持 ``style`` 等扩展字段，否则会触发
        ``params error, unknown content value`` 错误。因此这里仅生成符合
        官方文档规范的字段，``**bold**`` 标记会被解析为普通文本节点。

        Args:
            markdown_text: Markdown 文本

        Returns:
            list: 飞书富文本内容
        """
        import re

        link_pattern = re.compile(r"\[([^\]]+)\]\(([^\)]+)\)")

        content: List[List[Dict]] = []
        lines = (markdown_text or "").strip().split("\n")

        for line in lines:
            if not line.strip():
                continue

            paragraph: List[Dict] = []

            # 解析行内粗体标记 (**text**)，飞书自定义机器人不支持 style 字段，
            # 因此只保留文本内容，去除 ``**`` 标记。
            parts = line.split("**")
            for part in parts:
                if not part:
                    continue

                # 处理链接 [text](url)
                last_end = 0
                for match in link_pattern.finditer(part):
                    if match.start() > last_end:
                        paragraph.append(
                            {
                                "tag": "text",
                                "text": part[last_end : match.start()],
                            }
                        )
                    paragraph.append(
                        {
                            "tag": "a",
                            "text": match.group(1),
                            "href": match.group(2),
                        }
                    )
                    last_end = match.end()

                if last_end < len(part):
                    paragraph.append({"tag": "text", "text": part[last_end:]})

            if paragraph:
                content.append(paragraph)

        return content

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
    ) -> NotificationMessage:
        """
        构建新 13F 报告通知

        Args:
            fund_name: 基金名称
            cik: CIK 编号
            quarter: 季度
            filing_date: 申报日期
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

        Returns:
            NotificationMessage: 通知消息
        """
        title = f"📊 {fund_name} 发布了新的 13F 报告"

        content_parts = [
            f"**基金**: {fund_name}",
            f"**CIK**: {cik}",
            f"**季度**: {quarter}",
            f"**申报日期**: {filing_date.strftime('%Y-%m-%d')}",
            f"**总持仓价值**: ${total_value:,.0f}",
            f"**持仓股票数**: {holdings_count}",
        ]

        if top_holdings:
            content_parts.append("\n**当前主要持仓**:")
            for i, holding in enumerate(top_holdings, 1):
                name = NotificationBuilder._format_security_label(
                    holding.get("name", ""), holding.get("security_class")
                )
                value = holding.get("value", 0)
                percentage = holding.get("percentage", 0)
                content_parts.append(f"{i}. {name}: ${value:,.0f} ({percentage:.2f}%)")

        if changes_summary:
            content_parts.extend(
                NotificationBuilder._format_changes_summary(changes_summary)
            )

        if report_url:
            content_parts.append(f"\n[查看完整报告]({report_url})")

        content = "\n".join(content_parts)

        return NotificationMessage(title=title, content=content)

    @staticmethod
    def _format_changes_summary(changes_summary: Dict[str, Any]) -> List[str]:
        """将持仓变动摘要格式化为消息行。"""
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
            lines.append(
                "**总市值变化**: "
                f"{sign}${abs(total_value_change):,.0f} "
                f"({total_percentage_change:+.2f}%)"
            )

        lines.append(
            "**变动概览**: "
            f"新增 {counts.get('new', 0)} / "
            f"清仓 {counts.get('closed', 0)} / "
            f"增持 {counts.get('increased', 0)} / "
            f"减持 {counts.get('decreased', 0)}"
        )

        new_items = changes_summary.get("new") or []
        if new_items:
            lines.append("\n**新增持仓**:")
            for i, item in enumerate(new_items, 1):
                name = NotificationBuilder._format_security_label(
                    item.get("name", ""), item.get("security_class")
                )
                value = item.get("value", 0)
                percentage = item.get("percentage", 0)
                lines.append(f"{i}. {name}: ${value:,.0f} ({percentage:.2f}%)")

        closed_items = changes_summary.get("closed") or []
        if closed_items:
            lines.append("\n**清仓持仓**:")
            for i, item in enumerate(closed_items, 1):
                name = NotificationBuilder._format_security_label(
                    item.get("name", ""), item.get("security_class")
                )
                prev_value = item.get("prev_value", 0)
                lines.append(f"{i}. {name}: ${prev_value:,.0f}")

        increased_items = changes_summary.get("increased") or []
        if increased_items:
            lines.append("\n**增持持仓**:")
            for i, item in enumerate(increased_items, 1):
                name = NotificationBuilder._format_security_label(
                    item.get("name", ""), item.get("security_class")
                )
                value_change = item.get("value_change", 0)
                percentage_change = item.get("percentage_change", 0)
                lines.append(
                    f"{i}. {name}: +${value_change:,.0f} "
                    f"({percentage_change:+.2f}%)"
                )

        decreased_items = changes_summary.get("decreased") or []
        if decreased_items:
            lines.append("\n**减持持仓**:")
            for i, item in enumerate(decreased_items, 1):
                name = NotificationBuilder._format_security_label(
                    item.get("name", ""), item.get("security_class")
                )
                value_change = item.get("value_change", 0)
                percentage_change = item.get("percentage_change", 0)
                lines.append(
                    f"{i}. {name}: -${abs(value_change):,.0f} "
                    f"({percentage_change:+.2f}%)"
                )

        return lines

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

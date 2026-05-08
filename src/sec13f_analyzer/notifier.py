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
        # 使用富文本格式
        return {
            "msg_type": "post",
            "content": {
                "post": {
                    "zh_cn": {
                        "title": message.title,
                        "content": self._parse_markdown_to_feishu(message.content),
                    }
                }
            },
        }

    def _parse_markdown_to_feishu(self, markdown_text: str) -> List[List[Dict]]:
        """
        将简单的 Markdown 文本转换为飞书富文本格式

        Args:
            markdown_text: Markdown 文本

        Returns:
            list: 飞书富文本内容
        """
        content = []
        lines = markdown_text.strip().split("\n")

        for line in lines:
            if not line.strip():
                continue

            paragraph = []

            # 简单处理粗体
            parts = line.split("**")
            for i, part in enumerate(parts):
                if not part:
                    continue

                if i % 2 == 1:  # 粗体部分
                    paragraph.append({"tag": "text", "text": part, "style": ["bold"]})
                else:  # 普通文本
                    # 处理链接 [text](url)
                    if "[" in part and "](" in part and ")" in part:
                        import re

                        link_pattern = r"\[([^\]]+)\]\(([^\)]+)\)"
                        last_end = 0
                        for match in re.finditer(link_pattern, part):
                            # 添加链接前的文本
                            if match.start() > last_end:
                                paragraph.append(
                                    {
                                        "tag": "text",
                                        "text": part[last_end : match.start()],
                                    }
                                )
                            # 添加链接
                            paragraph.append(
                                {
                                    "tag": "a",
                                    "text": match.group(1),
                                    "href": match.group(2),
                                }
                            )
                            last_end = match.end()
                        # 添加剩余文本
                        if last_end < len(part):
                            paragraph.append({"tag": "text", "text": part[last_end:]})
                    else:
                        paragraph.append({"tag": "text", "text": part})

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
    def build_new_filing_notification(
        fund_name: str,
        cik: str,
        quarter: str,
        filing_date: datetime,
        total_value: float,
        holdings_count: int,
        top_holdings: Optional[List[Dict]] = None,
        report_url: Optional[str] = None,
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

        # 添加 top holdings
        if top_holdings:
            content_parts.append("\n**主要持仓**:")
            for i, holding in enumerate(top_holdings[:5], 1):
                name = holding.get("name", "")
                value = holding.get("value", 0)
                percentage = holding.get("percentage", 0)
                content_parts.append(f"{i}. {name}: ${value:,.0f} ({percentage:.2f}%)")

        # 添加报告链接
        if report_url:
            content_parts.append(f"\n[查看完整报告]({report_url})")

        content = "\n".join(content_parts)

        return NotificationMessage(title=title, content=content)

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

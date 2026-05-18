"""
监控服务配置加载器

处理监控服务的 YAML 配置文件
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List

import yaml


@dataclass
class PortfolioConfig:
    """投资组合配置"""

    name: str
    cik: str
    enabled: bool = True
    min_report_days: int = 30


@dataclass
class WebhookConfig:
    """Webhook 配置"""

    name: str
    type: str
    url: str
    enabled: bool = True
    send_test_on_start: bool = False


@dataclass
class ServiceConfig:
    """服务基本配置"""

    check_interval: int = 60
    user_agent: str = "SEC13F-Monitor/1.0.0"
    state_file: str = ".monitor_state.json"


@dataclass
class NotificationConfig:
    """通知配置"""

    include_holdings_summary: bool = True
    max_holdings_in_summary: int = 10
    include_report_link: bool = True
    # 是否在消息中包含与上一季度的持仓变动摘要
    include_changes_summary: bool = True
    # 持仓变动摘要中每个类别（新增/清仓/增持/减持）的最大条目数
    max_changes_in_summary: int = 5


@dataclass
class MonitorConfig:
    """完整的监控配置"""

    service: ServiceConfig
    portfolios: List[PortfolioConfig]
    webhooks: List[WebhookConfig]
    notification: NotificationConfig

    @property
    def enabled_portfolios(self) -> List[PortfolioConfig]:
        """获取启用的投资组合"""
        return [p for p in self.portfolios if p.enabled]

    @property
    def enabled_webhooks(self) -> List[WebhookConfig]:
        """获取启用的 webhook"""
        return [w for w in self.webhooks if w.enabled]


class MonitorConfigLoader:
    """监控配置加载器"""

    @staticmethod
    def load(config_file: str) -> MonitorConfig:
        """
        从 YAML 文件加载配置

        Args:
            config_file: 配置文件路径

        Returns:
            MonitorConfig: 配置对象

        Raises:
            FileNotFoundError: 配置文件不存在
            ValueError: 配置文件格式错误
        """
        config_path = Path(config_file)
        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_file}")

        try:
            with open(config_path) as f:
                data = yaml.safe_load(f)

            if not data:
                raise ValueError("配置文件为空")

            # 解析配置
            service = MonitorConfigLoader._parse_service(data.get("service", {}))
            portfolios = MonitorConfigLoader._parse_portfolios(
                data.get("portfolios", [])
            )
            webhooks = MonitorConfigLoader._parse_webhooks(data.get("webhooks", []))
            notification = MonitorConfigLoader._parse_notification(
                data.get("notification", {})
            )

            config = MonitorConfig(
                service=service,
                portfolios=portfolios,
                webhooks=webhooks,
                notification=notification,
            )

            # 验证配置
            MonitorConfigLoader._validate(config)

            return config

        except yaml.YAMLError as e:
            raise ValueError(f"YAML 解析错误: {e}")
        except Exception as e:
            raise ValueError(f"配置加载失败: {e}")

    @staticmethod
    def _parse_service(data: dict) -> ServiceConfig:
        """解析服务配置"""
        return ServiceConfig(
            check_interval=data.get("check_interval", 60),
            user_agent=data.get("user_agent", "SEC13F-Monitor/1.0.0"),
            state_file=data.get("state_file", ".monitor_state.json"),
        )

    @staticmethod
    def _parse_portfolios(data: list) -> List[PortfolioConfig]:
        """解析投资组合列表"""
        portfolios = []
        for item in data:
            portfolio = PortfolioConfig(
                name=item["name"],
                cik=item["cik"],
                enabled=item.get("enabled", True),
                min_report_days=item.get("min_report_days", 30),
            )
            portfolios.append(portfolio)
        return portfolios

    @staticmethod
    def _parse_webhooks(data: list) -> List[WebhookConfig]:
        """解析 webhook 列表"""
        webhooks = []
        for item in data:
            webhook = WebhookConfig(
                name=item["name"],
                type=item["type"],
                url=item["url"],
                enabled=item.get("enabled", True),
                send_test_on_start=item.get("send_test_on_start", False),
            )
            webhooks.append(webhook)
        return webhooks

    @staticmethod
    def _parse_notification(data: dict) -> NotificationConfig:
        """解析通知配置"""
        return NotificationConfig(
            include_holdings_summary=data.get("include_holdings_summary", True),
            max_holdings_in_summary=data.get("max_holdings_in_summary", 10),
            include_report_link=data.get("include_report_link", True),
            include_changes_summary=data.get("include_changes_summary", True),
            max_changes_in_summary=data.get("max_changes_in_summary", 5),
        )

    @staticmethod
    def _validate(config: MonitorConfig):
        """
        验证配置有效性

        Raises:
            ValueError: 配置无效
        """
        # 检查是否有启用的组合
        if not config.enabled_portfolios:
            raise ValueError("至少需要配置一个启用的投资组合")

        # 检查是否有启用的 webhook
        if not config.enabled_webhooks:
            raise ValueError("至少需要配置一个启用的 webhook")

        # 检查 CIK 格式
        for portfolio in config.portfolios:
            if not portfolio.cik:
                raise ValueError(f"投资组合 '{portfolio.name}' 的 CIK 不能为空")

        # 检查 webhook URL
        for webhook in config.webhooks:
            if not webhook.url.startswith("http"):
                raise ValueError(f"Webhook '{webhook.name}' 的 URL 格式无效")

        # 检查检查间隔
        if config.service.check_interval < 1:
            raise ValueError("检查间隔必须大于等于 1 分钟")

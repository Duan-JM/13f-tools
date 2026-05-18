"""
测试监控服务
"""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sec13f_analyzer.monitor import MonitorState, SEC13FMonitor
from sec13f_analyzer.monitor_config import (
    MonitorConfig,
    NotificationConfig,
    PortfolioConfig,
    ServiceConfig,
    WebhookConfig,
)


@pytest.fixture
def sample_monitor_config():
    """创建示例监控配置"""
    service = ServiceConfig(
        check_interval=30, user_agent="Test-Agent/1.0", state_file=".test_state.json"
    )

    portfolios = [
        PortfolioConfig(
            name="测试基金", cik="0001234567", enabled=True, min_report_days=30
        )
    ]

    webhooks = [
        WebhookConfig(
            name="测试webhook",
            type="feishu",
            url="https://example.com/webhook",
            enabled=True,
        )
    ]

    notification = NotificationConfig(
        include_holdings_summary=True,
        max_holdings_in_summary=5,
        include_report_link=True,
    )

    return MonitorConfig(
        service=service,
        portfolios=portfolios,
        webhooks=webhooks,
        notification=notification,
    )


@pytest.fixture
def temp_state_file():
    """创建临时状态文件"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        temp_path = f.name

    yield temp_path

    # 清理
    if Path(temp_path).exists():
        Path(temp_path).unlink()


def test_monitor_state_init(temp_state_file):
    """测试状态管理器初始化"""
    state = MonitorState(temp_state_file)

    assert state.state_file == Path(temp_state_file)
    assert isinstance(state.state, dict)


def test_monitor_state_update(temp_state_file):
    """测试状态更新"""
    state = MonitorState(temp_state_file)

    state.update("0001234567", "2024Q3")

    assert "0001234567" in state.state
    assert state.state["0001234567"]["last_quarter"] == "2024Q3"
    assert "last_check" in state.state["0001234567"]


def test_monitor_state_get_last_quarter(temp_state_file):
    """测试获取上次检查的季度"""
    state = MonitorState(temp_state_file)

    state.update("0001234567", "2024Q3")
    last_quarter = state.get_last_quarter("0001234567")

    assert last_quarter == "2024Q3"

    # 测试不存在的 CIK
    assert state.get_last_quarter("9999999999") is None


def test_monitor_state_persistence(temp_state_file):
    """测试状态持久化"""
    state1 = MonitorState(temp_state_file)
    state1.update("0001234567", "2024Q3")

    # 创建新的状态管理器实例
    state2 = MonitorState(temp_state_file)
    last_quarter = state2.get_last_quarter("0001234567")

    assert last_quarter == "2024Q3"


@patch("sec13f_analyzer.monitor.SEC13FAnalyzer")
def test_monitor_init(mock_analyzer, sample_monitor_config):
    """测试监控服务初始化"""
    monitor = SEC13FMonitor(sample_monitor_config)

    assert monitor.config == sample_monitor_config
    assert len(monitor.notifiers) > 0
    assert monitor.running is False


@patch("sec13f_analyzer.monitor.SEC13FAnalyzer")
@patch("sec13f_analyzer.monitor.FeishuWebhookNotifier")
def test_monitor_check_new_report(
    mock_notifier_class, mock_analyzer_class, sample_monitor_config, temp_state_file
):
    """测试检测新报告"""
    # 修改配置使用临时状态文件
    sample_monitor_config.service.state_file = temp_state_file

    # Mock analyzer
    mock_analyzer = MagicMock()
    mock_analyzer_class.return_value = mock_analyzer

    # Mock 报告数据：包含上一季度，便于覆盖变动摘要分支
    mock_analyzer.data_fetcher.get_13f_filings.return_value = [
        {"quarter": "2024Q3", "filing_date": datetime(2024, 11, 14)},
        {"quarter": "2024Q2", "filing_date": datetime(2024, 8, 14)},
    ]

    # Mock 持仓数据
    mock_holdings = MagicMock()
    mock_holdings.total_value = 1000000000
    mock_holdings.holdings = [MagicMock() for _ in range(100)]
    mock_analyzer.get_holdings.return_value = mock_holdings
    mock_analyzer.get_top_holdings.return_value = []
    # 没有可用的变动数据时返回 None，不应触发异常
    mock_analyzer.analyze_holdings_changes.return_value = None

    # Mock notifier
    mock_notifier = MagicMock()
    mock_notifier_class.return_value = mock_notifier

    monitor = SEC13FMonitor(sample_monitor_config)
    monitor.notifiers = [mock_notifier]

    # 检查
    result = monitor._check_portfolio(sample_monitor_config.portfolios[0])

    assert result is True
    # 验证通知被发送
    assert mock_notifier.send.called
    # 应基于上一季度尝试计算变动
    mock_analyzer.analyze_holdings_changes.assert_called_once_with(
        "0001234567", "2024Q2", "2024Q3"
    )


@patch("sec13f_analyzer.monitor.SEC13FAnalyzer")
@patch("sec13f_analyzer.monitor.FeishuWebhookNotifier")
def test_monitor_no_new_report(
    mock_notifier_class, mock_analyzer_class, sample_monitor_config, temp_state_file
):
    """测试没有新报告的情况"""
    sample_monitor_config.service.state_file = temp_state_file

    # Mock analyzer
    mock_analyzer = MagicMock()
    mock_analyzer_class.return_value = mock_analyzer

    mock_analyzer.data_fetcher.get_13f_filings.return_value = [
        {"quarter": "2024Q3", "filing_date": datetime(2024, 11, 14)}
    ]

    mock_notifier = MagicMock()
    mock_notifier_class.return_value = mock_notifier

    monitor = SEC13FMonitor(sample_monitor_config)
    monitor.notifiers = [mock_notifier]

    # 第一次检查
    monitor.state.update("0001234567", "2024Q3")

    # 第二次检查（应该不会有新通知）
    result = monitor._check_portfolio(sample_monitor_config.portfolios[0])

    assert result is False


def test_find_previous_quarter_skips_same_quarter():
    """同季度的修订报告应被跳过"""
    filings = [
        {"quarter": "2024Q3", "filing_date": datetime(2024, 12, 1)},
        {"quarter": "2024Q3", "filing_date": datetime(2024, 11, 14)},
        {"quarter": "2024Q2", "filing_date": datetime(2024, 8, 14)},
        {"quarter": "2024Q1", "filing_date": datetime(2024, 5, 14)},
    ]
    assert SEC13FMonitor._find_previous_quarter(filings, "2024Q3") == "2024Q2"


def test_find_previous_quarter_returns_none_when_only_latest():
    """只有最新季度的记录时应返回 None"""
    filings = [
        {"quarter": "2024Q3", "filing_date": datetime(2024, 11, 14)},
    ]
    assert SEC13FMonitor._find_previous_quarter(filings, "2024Q3") is None


@patch("sec13f_analyzer.monitor.SEC13FAnalyzer")
@patch("sec13f_analyzer.monitor.FeishuWebhookNotifier")
def test_monitor_includes_changes_summary_in_notification(
    mock_notifier_class,
    mock_analyzer_class,
    sample_monitor_config,
    temp_state_file,
    sample_holdings,
    sample_holdings_change,
):
    """变动摘要应作为参数传入通知构建器，并最终出现在通知内容中"""
    sample_monitor_config.service.state_file = temp_state_file

    mock_analyzer = MagicMock()
    mock_analyzer_class.return_value = mock_analyzer

    mock_analyzer.data_fetcher.get_13f_filings.return_value = [
        {"quarter": "2024Q3", "filing_date": datetime(2024, 11, 14)},
        {"quarter": "2024Q2", "filing_date": datetime(2024, 8, 14)},
    ]
    mock_analyzer.get_holdings.return_value = sample_holdings
    mock_analyzer.get_top_holdings.return_value = sample_holdings.top_holdings(5)
    mock_analyzer.analyze_holdings_changes.return_value = sample_holdings_change

    mock_notifier = MagicMock()
    mock_notifier_class.return_value = mock_notifier

    monitor = SEC13FMonitor(sample_monitor_config)
    monitor.notifiers = [mock_notifier]

    result = monitor._check_portfolio(sample_monitor_config.portfolios[0])

    assert result is True
    mock_analyzer.analyze_holdings_changes.assert_called_once_with(
        "0001234567", "2024Q2", "2024Q3"
    )

    # 通知内容应同时包含当前持仓和变动摘要
    sent_message = mock_notifier.send.call_args.args[0]
    assert "当前主要持仓" in sent_message.content
    assert "持仓变动" in sent_message.content
    assert "Amazon.com Inc" in sent_message.content  # new
    assert "Tesla Inc" in sent_message.content  # closed
    assert "Microsoft Corporation" in sent_message.content  # increased
    assert "Apple Inc." in sent_message.content  # decreased


@patch("sec13f_analyzer.monitor.SEC13FAnalyzer")
@patch("sec13f_analyzer.monitor.FeishuWebhookNotifier")
def test_monitor_skips_changes_summary_when_disabled(
    mock_notifier_class,
    mock_analyzer_class,
    sample_monitor_config,
    temp_state_file,
    sample_holdings,
):
    """当配置关闭变动摘要时不应调用 analyze_holdings_changes"""
    sample_monitor_config.service.state_file = temp_state_file
    sample_monitor_config.notification.include_changes_summary = False

    mock_analyzer = MagicMock()
    mock_analyzer_class.return_value = mock_analyzer
    mock_analyzer.data_fetcher.get_13f_filings.return_value = [
        {"quarter": "2024Q3", "filing_date": datetime(2024, 11, 14)},
        {"quarter": "2024Q2", "filing_date": datetime(2024, 8, 14)},
    ]
    mock_analyzer.get_holdings.return_value = sample_holdings
    mock_analyzer.get_top_holdings.return_value = []

    mock_notifier = MagicMock()
    mock_notifier_class.return_value = mock_notifier

    monitor = SEC13FMonitor(sample_monitor_config)
    monitor.notifiers = [mock_notifier]

    monitor._check_portfolio(sample_monitor_config.portfolios[0])

    mock_analyzer.analyze_holdings_changes.assert_not_called()

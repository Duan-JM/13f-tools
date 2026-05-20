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


def _make_filing(
    quarter,
    filing_date,
    accession,
    *,
    is_amendment=False,
    report_quarter=None,
    period_end_date=None,
):
    """构造测试用的 filing dict。

    新版本的 monitor 依赖 ``accession_number`` 与 ``report_quarter``
    字段做幂等判新；mocks 都通过这个 helper 生成，保证字段齐全。
    """
    return {
        "quarter": quarter,
        "filing_date": filing_date,
        "accession_number": accession,
        "is_amendment": is_amendment,
        "url": (
            f"https://www.sec.gov/Archives/edgar/data/1234567/{accession}/"
            f"{accession}-index.htm"
        ),
        "report_quarter": report_quarter if report_quarter is not None else quarter,
        "period_end_date": period_end_date,
    }


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


def test_monitor_state_tracks_seen_accessions(temp_state_file):
    """状态文件应能去重写入并持久化 ``seen_accessions``。"""
    state = MonitorState(temp_state_file)

    state.mark_accessions_seen("0001234567", ["acc-1", "acc-2", "acc-1"])
    state.mark_accessions_seen("0001234567", ["acc-2", "acc-3"])

    seen = state.get_seen_accessions("0001234567")
    assert seen == ["acc-1", "acc-2", "acc-3"]
    assert state.has_seen_accessions("0001234567") is True

    # 重新加载后仍保留
    reloaded = MonitorState(temp_state_file)
    assert reloaded.get_seen_accessions("0001234567") == ["acc-1", "acc-2", "acc-3"]


def test_monitor_state_has_seen_accessions_false_for_legacy(temp_state_file):
    """没有 ``seen_accessions`` 键的旧 state 应被识别为待迁移。"""
    state = MonitorState(temp_state_file)
    state.update("0001234567", "2024Q3")  # 旧 schema：仅有 last_quarter
    assert state.has_seen_accessions("0001234567") is False
    assert state.has_cik("0001234567") is True


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
    """全新 CIK 首次检查时仅对最新一份 filing 发通知。"""
    sample_monitor_config.service.state_file = temp_state_file

    mock_analyzer = MagicMock()
    mock_analyzer_class.return_value = mock_analyzer

    mock_analyzer.data_fetcher.get_13f_filings.return_value = [
        _make_filing("2024Q3", datetime(2024, 11, 14), "0000950123-24-000003"),
        _make_filing("2024Q2", datetime(2024, 8, 14), "0000950123-24-000002"),
    ]

    mock_holdings = MagicMock()
    mock_holdings.total_value = 1000000000
    mock_holdings.holdings = [MagicMock() for _ in range(100)]
    mock_holdings.amendment_metadata = []
    mock_analyzer.get_holdings.return_value = mock_holdings
    mock_analyzer.get_top_holdings.return_value = []
    mock_analyzer.analyze_holdings_changes.return_value = None

    mock_notifier = MagicMock()
    mock_notifier_class.return_value = mock_notifier

    monitor = SEC13FMonitor(sample_monitor_config)
    monitor.notifiers = [mock_notifier]

    result = monitor._check_portfolio(sample_monitor_config.portfolios[0])

    assert result is True
    # 首跑门控：只为最新 quarter 发一条通知
    assert mock_notifier.send.call_count == 1
    # 应基于上一季度尝试计算变动
    mock_analyzer.analyze_holdings_changes.assert_called_once_with(
        "0001234567", "2024Q2", "2024Q3"
    )
    # 历史 filing 也要被标记 seen，避免下一轮重复推
    seen = monitor.state.get_seen_accessions("0001234567")
    assert "0000950123-24-000003" in seen
    assert "0000950123-24-000002" in seen


@patch("sec13f_analyzer.monitor.SEC13FAnalyzer")
@patch("sec13f_analyzer.monitor.FeishuWebhookNotifier")
def test_monitor_no_new_report(
    mock_notifier_class, mock_analyzer_class, sample_monitor_config, temp_state_file
):
    """所有 accession 已见时不应再推送通知。"""
    sample_monitor_config.service.state_file = temp_state_file

    mock_analyzer = MagicMock()
    mock_analyzer_class.return_value = mock_analyzer

    mock_analyzer.data_fetcher.get_13f_filings.return_value = [
        _make_filing("2024Q3", datetime(2024, 11, 14), "0000950123-24-000003"),
    ]

    mock_notifier = MagicMock()
    mock_notifier_class.return_value = mock_notifier

    monitor = SEC13FMonitor(sample_monitor_config)
    monitor.notifiers = [mock_notifier]

    # 预先标记 accession 已见
    monitor.state.mark_accessions_seen("0001234567", ["0000950123-24-000003"])

    result = monitor._check_portfolio(sample_monitor_config.portfolios[0])

    assert result is False
    mock_notifier.send.assert_not_called()


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
        _make_filing("2024Q3", datetime(2024, 11, 14), "0000950123-24-000003"),
        _make_filing("2024Q2", datetime(2024, 8, 14), "0000950123-24-000002"),
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
    assert "Amazon.com Inc (COM)" in sent_message.content  # new
    assert "Tesla Inc (COM)" in sent_message.content  # closed
    assert "Microsoft Corporation (COM)" in sent_message.content  # increased
    assert "Apple Inc. (COM)" in sent_message.content  # decreased


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
        _make_filing("2024Q3", datetime(2024, 11, 14), "0000950123-24-000003"),
        _make_filing("2024Q2", datetime(2024, 8, 14), "0000950123-24-000002"),
    ]
    mock_analyzer.get_holdings.return_value = sample_holdings
    mock_analyzer.get_top_holdings.return_value = []

    mock_notifier = MagicMock()
    mock_notifier_class.return_value = mock_notifier

    monitor = SEC13FMonitor(sample_monitor_config)
    monitor.notifiers = [mock_notifier]

    monitor._check_portfolio(sample_monitor_config.portfolios[0])

    mock_analyzer.analyze_holdings_changes.assert_not_called()


@patch("sec13f_analyzer.monitor.SEC13FAnalyzer")
@patch("sec13f_analyzer.monitor.FeishuWebhookNotifier")
def test_monitor_emits_amendment_after_original(
    mock_notifier_class,
    mock_analyzer_class,
    sample_monitor_config,
    temp_state_file,
    sample_holdings,
):
    """回归 Bug B：HR 已推送后到达的 HR/A 必须再触发一条修订通知。"""
    sample_monitor_config.service.state_file = temp_state_file

    mock_analyzer = MagicMock()
    mock_analyzer_class.return_value = mock_analyzer
    mock_holdings = sample_holdings
    mock_holdings.amendment_metadata = []
    mock_analyzer.get_holdings.return_value = mock_holdings
    mock_analyzer.get_top_holdings.return_value = []
    mock_analyzer.analyze_holdings_changes.return_value = None

    # 第 1 轮：只有原始 HR
    mock_analyzer.data_fetcher.get_13f_filings.return_value = [
        _make_filing("2024Q3", datetime(2024, 11, 14), "0000950123-24-000003"),
    ]

    mock_notifier = MagicMock()
    mock_notifier_class.return_value = mock_notifier

    monitor = SEC13FMonitor(sample_monitor_config)
    monitor.notifiers = [mock_notifier]

    assert monitor._check_portfolio(sample_monitor_config.portfolios[0]) is True
    first_call_message = mock_notifier.send.call_args.args[0]
    assert "修订" not in first_call_message.title

    # 第 2 轮：同季度新增 HR/A，并且 fetcher 拉到的列表里两份都在
    mock_notifier.send.reset_mock()
    mock_analyzer.data_fetcher.get_13f_filings.return_value = [
        _make_filing(
            "2024Q3",
            datetime(2024, 12, 5),
            "0000950123-24-000004",
            is_amendment=True,
        ),
        _make_filing("2024Q3", datetime(2024, 11, 14), "0000950123-24-000003"),
    ]

    assert monitor._check_portfolio(sample_monitor_config.portfolios[0]) is True
    assert mock_notifier.send.call_count == 1
    second_call_message = mock_notifier.send.call_args.args[0]
    assert "修订" in second_call_message.title


@patch("sec13f_analyzer.monitor.SEC13FAnalyzer")
@patch("sec13f_analyzer.monitor.FeishuWebhookNotifier")
def test_monitor_uses_real_report_quarter_for_late_amendment(
    mock_notifier_class,
    mock_analyzer_class,
    sample_monitor_config,
    temp_state_file,
    sample_holdings,
):
    """回归 Bug C：跨时段提交的 HR/A 应按 ``report_quarter`` 归类。

    HR/A 的 ``quarter``（基于 filing_date 反推）是 ``2025Q1``，
    但 ``report_quarter``（基于 periodOfReport）才是真实的 ``2024Q3``。
    monitor 必须按 ``report_quarter`` 分组并取 ``2024Q3`` 的持仓。
    """
    sample_monitor_config.service.state_file = temp_state_file

    mock_analyzer = MagicMock()
    mock_analyzer_class.return_value = mock_analyzer
    sample_holdings.amendment_metadata = []
    mock_analyzer.get_holdings.return_value = sample_holdings
    mock_analyzer.get_top_holdings.return_value = []
    mock_analyzer.analyze_holdings_changes.return_value = None

    mock_analyzer.data_fetcher.get_13f_filings.return_value = [
        _make_filing(
            "2025Q1",  # 由 filing_date=2025-02-10 反推
            datetime(2025, 2, 10),
            "0000950123-25-000001",
            is_amendment=True,
            report_quarter="2024Q3",  # 真实 periodOfReport
            period_end_date=datetime(2024, 9, 30),
        ),
        _make_filing(
            "2024Q3",
            datetime(2024, 11, 14),
            "0000950123-24-000003",
        ),
    ]

    mock_notifier = MagicMock()
    mock_notifier_class.return_value = mock_notifier

    # 模拟 state 里已有 2024Q3 的原始 HR
    monitor = SEC13FMonitor(sample_monitor_config)
    monitor.notifiers = [mock_notifier]
    monitor.state.mark_accessions_seen("0001234567", ["0000950123-24-000003"])

    assert monitor._check_portfolio(sample_monitor_config.portfolios[0]) is True
    # 应该按真实季度 2024Q3 取持仓，而不是 2025Q1
    mock_analyzer.get_holdings.assert_called_with(
        "0001234567", "2024Q3", use_cache=False
    )
    sent_message = mock_notifier.send.call_args.args[0]
    assert "修订" in sent_message.title
    assert "2024Q3" in sent_message.content


@patch("sec13f_analyzer.monitor.SEC13FAnalyzer")
@patch("sec13f_analyzer.monitor.FeishuWebhookNotifier")
def test_monitor_legacy_state_migration_does_not_backfill(
    mock_notifier_class,
    mock_analyzer_class,
    sample_monitor_config,
    temp_state_file,
    sample_holdings,
):
    """旧 schema 升级时应一次性把历史 accession 标记 seen，不灌水推送。"""
    sample_monitor_config.service.state_file = temp_state_file

    mock_analyzer = MagicMock()
    mock_analyzer_class.return_value = mock_analyzer
    sample_holdings.amendment_metadata = []
    mock_analyzer.get_holdings.return_value = sample_holdings
    mock_analyzer.get_top_holdings.return_value = []
    mock_analyzer.analyze_holdings_changes.return_value = None
    mock_analyzer.data_fetcher.get_13f_filings.return_value = [
        _make_filing("2024Q3", datetime(2024, 11, 14), "0000950123-24-000003"),
        _make_filing("2024Q2", datetime(2024, 8, 14), "0000950123-24-000002"),
        _make_filing("2024Q1", datetime(2024, 5, 14), "0000950123-24-000001"),
    ]

    mock_notifier = MagicMock()
    mock_notifier_class.return_value = mock_notifier

    monitor = SEC13FMonitor(sample_monitor_config)
    monitor.notifiers = [mock_notifier]

    # 旧 state：仅记录 last_quarter，没有 seen_accessions
    monitor.state.update("0001234567", "2024Q3")
    assert monitor.state.has_seen_accessions("0001234567") is False

    result = monitor._check_portfolio(sample_monitor_config.portfolios[0])

    assert result is False
    mock_notifier.send.assert_not_called()
    seen = set(monitor.state.get_seen_accessions("0001234567"))
    assert "0000950123-24-000001" in seen
    assert "0000950123-24-000002" in seen
    assert "0000950123-24-000003" in seen


@patch("sec13f_analyzer.monitor.SEC13FAnalyzer")
@patch("sec13f_analyzer.monitor.FeishuWebhookNotifier")
def test_monitor_does_not_mark_seen_on_send_failure(
    mock_notifier_class,
    mock_analyzer_class,
    sample_monitor_config,
    temp_state_file,
    sample_holdings,
):
    """webhook 全部发送失败时不应把 accession 标记 seen。"""
    sample_monitor_config.service.state_file = temp_state_file

    mock_analyzer = MagicMock()
    mock_analyzer_class.return_value = mock_analyzer
    sample_holdings.amendment_metadata = []
    mock_analyzer.get_holdings.return_value = sample_holdings
    mock_analyzer.get_top_holdings.return_value = []
    mock_analyzer.analyze_holdings_changes.return_value = None
    mock_analyzer.data_fetcher.get_13f_filings.return_value = [
        _make_filing("2024Q3", datetime(2024, 11, 14), "0000950123-24-000003"),
    ]

    mock_notifier = MagicMock()
    mock_notifier.send.side_effect = RuntimeError("webhook down")
    mock_notifier_class.return_value = mock_notifier

    monitor = SEC13FMonitor(sample_monitor_config)
    monitor.notifiers = [mock_notifier]

    result = monitor._check_portfolio(sample_monitor_config.portfolios[0])

    assert result is False
    # 历史项已通过 first-run gate 被标记
    seen = monitor.state.get_seen_accessions("0001234567")
    # 因发送失败，最新的那份不应被加入 seen，下一轮应该重试
    assert "0000950123-24-000003" not in seen


@patch("sec13f_analyzer.monitor.SEC13FAnalyzer")
@patch("sec13f_analyzer.monitor.FeishuWebhookNotifier")
def test_monitor_min_report_days_no_longer_blocks_new_quarter(
    mock_notifier_class,
    mock_analyzer_class,
    sample_monitor_config,
    temp_state_file,
    sample_holdings,
):
    """回归 Bug A：删除 min_report_days guard 后，紧随其后的新季度必须能推。"""
    sample_monitor_config.service.state_file = temp_state_file
    sample_monitor_config.portfolios[0].min_report_days = 30  # 旧默认值

    mock_analyzer = MagicMock()
    mock_analyzer_class.return_value = mock_analyzer
    sample_holdings.amendment_metadata = []
    mock_analyzer.get_holdings.return_value = sample_holdings
    mock_analyzer.get_top_holdings.return_value = []
    mock_analyzer.analyze_holdings_changes.return_value = None

    mock_notifier = MagicMock()
    mock_notifier_class.return_value = mock_notifier

    monitor = SEC13FMonitor(sample_monitor_config)
    monitor.notifiers = [mock_notifier]

    # 模拟"上一轮刚做完 Q2 通知"，last_check 刷新为现在
    monitor.state.mark_accessions_seen("0001234567", ["0000950123-24-000002"])
    monitor.state.update("0001234567", "2024Q2")

    # 紧接着 Q3 出现（间隔远小于 min_report_days 默认 30 天）
    mock_analyzer.data_fetcher.get_13f_filings.return_value = [
        _make_filing("2024Q3", datetime(2024, 11, 14), "0000950123-24-000003"),
        _make_filing("2024Q2", datetime(2024, 8, 14), "0000950123-24-000002"),
    ]

    result = monitor._check_portfolio(sample_monitor_config.portfolios[0])

    assert result is True
    assert mock_notifier.send.call_count == 1

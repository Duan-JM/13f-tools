"""
测试通知器
"""

import responses

from sec13f_analyzer.notifier import (
    FeishuWebhookNotifier,
    NotificationBuilder,
    NotificationMessage,
)


def test_notification_message():
    """测试通知消息创建"""
    msg = NotificationMessage(title="测试标题", content="测试内容")

    assert msg.title == "测试标题"
    assert msg.content == "测试内容"
    assert msg.timestamp is not None


@responses.activate
def test_feishu_notifier_success():
    """测试飞书通知发送成功"""
    webhook_url = "https://example.com/webhook"

    # Mock 成功响应
    responses.add(
        responses.POST,
        webhook_url,
        json={"code": 0, "msg": "success"},
        status=200,
    )

    notifier = FeishuWebhookNotifier(webhook_url)
    msg = NotificationMessage(title="测试", content="测试内容")

    result = notifier.send(msg)

    assert result is True
    assert len(responses.calls) == 1


@responses.activate
def test_feishu_notifier_failure():
    """测试飞书通知发送失败"""
    webhook_url = "https://example.com/webhook"

    # Mock 失败响应
    responses.add(
        responses.POST,
        webhook_url,
        json={"code": 1, "msg": "error"},
        status=200,
    )

    notifier = FeishuWebhookNotifier(webhook_url)
    msg = NotificationMessage(title="测试", content="测试内容")

    result = notifier.send(msg)

    assert result is False


def test_build_new_filing_notification():
    """测试构建新报告通知"""
    from datetime import datetime

    msg = NotificationBuilder.build_new_filing_notification(
        fund_name="测试基金",
        cik="0001234567",
        quarter="2024Q3",
        filing_date=datetime(2024, 11, 14),
        total_value=1000000000,
        holdings_count=100,
    )

    assert "测试基金" in msg.title
    assert "13F" in msg.title
    assert "0001234567" in msg.content
    assert "2024Q3" in msg.content
    assert "$1,000,000,000" in msg.content


def test_build_new_filing_notification_with_changes_summary():
    """新报告通知应包含与上一季度的持仓变动摘要"""
    from datetime import datetime

    changes_summary = {
        "from_quarter": "2024Q2",
        "to_quarter": "2024Q3",
        "total_prev_value": 900_000_000,
        "total_curr_value": 1_000_000_000,
        "total_value_change": 100_000_000,
        "total_percentage_change": 11.11,
        "counts": {"new": 1, "closed": 1, "increased": 1, "decreased": 1},
        "new": [
            {
                "name": "Amazon.com Inc",
                "security_class": "COM",
                "value": 75_000_000,
                "percentage": 7.5,
            },
        ],
        "closed": [
            {"name": "Tesla Inc", "security_class": "COM", "prev_value": 20_000_000},
        ],
        "increased": [
            {
                "name": "Microsoft Corporation",
                "security_class": "COM",
                "prev_value": 90_000_000,
                "curr_value": 120_000_000,
                "value_change": 30_000_000,
                "percentage_change": 33.33,
            },
        ],
        "decreased": [
            {
                "name": "Apple Inc.",
                "security_class": "COM",
                "prev_value": 180_000_000,
                "curr_value": 150_000_000,
                "value_change": -30_000_000,
                "percentage_change": -16.67,
            },
        ],
    }

    msg = NotificationBuilder.build_new_filing_notification(
        fund_name="测试基金",
        cik="0001234567",
        quarter="2024Q3",
        filing_date=datetime(2024, 11, 14),
        total_value=1_000_000_000,
        holdings_count=100,
        changes_summary=changes_summary,
    )

    assert "持仓变动" in msg.content
    assert "2024Q2 → 2024Q3" in msg.content
    assert "新增 1" in msg.content
    assert "清仓 1" in msg.content
    assert "增持 1" in msg.content
    assert "减持 1" in msg.content

    # 各类别条目
    assert "Amazon.com Inc (COM)" in msg.content
    assert "Tesla Inc (COM)" in msg.content
    assert "Microsoft Corporation (COM)" in msg.content
    assert "Apple Inc. (COM)" in msg.content

    # 总体变化的方向标识
    assert "+$100,000,000" in msg.content
    assert "+11.11%" in msg.content
    # 减持金额以 - 前缀展示
    assert "-$30,000,000" in msg.content


def test_build_new_filing_notification_includes_title_of_class_in_top_holdings():
    """当前主要持仓应展示 TITLE OF CLASS。"""
    from datetime import datetime

    msg = NotificationBuilder.build_new_filing_notification(
        fund_name="测试基金",
        cik="0001234567",
        quarter="2024Q3",
        filing_date=datetime(2024, 11, 14),
        total_value=1_000_000_000,
        holdings_count=100,
        top_holdings=[
            {
                "name": "Alphabet Inc",
                "security_class": "CLASS A",
                "value": 80_000_000,
                "percentage": 8.0,
            }
        ],
    )

    assert "Alphabet Inc (CLASS A)" in msg.content


def test_build_new_filing_notification_skips_empty_change_categories():
    """空的变动类别不应输出对应小节"""
    from datetime import datetime

    changes_summary = {
        "from_quarter": "2024Q2",
        "to_quarter": "2024Q3",
        "total_prev_value": 1_000_000_000,
        "total_curr_value": 1_000_000_000,
        "total_value_change": 0,
        "total_percentage_change": 0.0,
        "counts": {"new": 0, "closed": 0, "increased": 0, "decreased": 0},
        "new": [],
        "closed": [],
        "increased": [],
        "decreased": [],
    }

    msg = NotificationBuilder.build_new_filing_notification(
        fund_name="测试基金",
        cik="0001234567",
        quarter="2024Q3",
        filing_date=datetime(2024, 11, 14),
        total_value=1_000_000_000,
        holdings_count=100,
        changes_summary=changes_summary,
    )

    assert "持仓变动" in msg.content
    assert "**新增持仓**" not in msg.content
    assert "**清仓持仓**" not in msg.content
    assert "**增持持仓**" not in msg.content
    assert "**减持持仓**" not in msg.content


def test_build_service_start_notification():
    """测试构建服务启动通知"""
    msg = NotificationBuilder.build_service_start_notification(
        portfolios_count=5, check_interval=60
    )

    assert "启动" in msg.title
    assert "5" in msg.content
    assert "60" in msg.content


def test_filing_notification_highlights_filing_date():
    """issue #8：申报日期应使用颜色高亮，并附带星期，降低看错风险。"""
    from datetime import datetime

    msg = NotificationBuilder.build_new_filing_notification(
        fund_name="测试基金",
        cik="0001234567",
        quarter="2024Q3",
        filing_date=datetime(2024, 11, 14),
        total_value=1_000_000_000,
        holdings_count=100,
    )

    # 申报日期使用红色高亮
    assert "<font color='red'>" in msg.content
    assert "2024-11-14" in msg.content
    # 周四 (2024-11-14) 应附带星期标签
    assert "周四" in msg.content


def test_filing_notification_distinguishes_period_and_filing_dates():
    """issue #8：报告期截止日期与申报日期应清晰区分，避免混淆。"""
    from datetime import datetime

    msg = NotificationBuilder.build_new_filing_notification(
        fund_name="测试基金",
        cik="0001234567",
        quarter="2024Q3",
        filing_date=datetime(2024, 11, 14),
        total_value=1_000_000_000,
        holdings_count=100,
        period_end_date=datetime(2024, 9, 30),
    )

    assert "报告期" in msg.content
    assert "申报日期" in msg.content
    # 报告期截止日期应展示真实的 period_end_date
    assert "2024-09-30" in msg.content
    # 申报日期与报告期截止日期均出现，且不应彼此混用
    assert "2024-11-14" in msg.content


def test_filing_notification_falls_back_to_quarter_end_date():
    """未提供 ``period_end_date`` 时应按自然季度末展示。"""
    from datetime import datetime

    msg = NotificationBuilder.build_new_filing_notification(
        fund_name="测试基金",
        cik="0001234567",
        quarter="2024Q3",
        filing_date=datetime(2024, 11, 14),
        total_value=1_000_000_000,
        holdings_count=100,
    )

    assert "2024-09-30" in msg.content


def test_filing_notification_renders_top_holdings_as_table():
    """issue #8：主要持仓应使用 Markdown 表格呈现。"""
    from datetime import datetime

    msg = NotificationBuilder.build_new_filing_notification(
        fund_name="测试基金",
        cik="0001234567",
        quarter="2024Q3",
        filing_date=datetime(2024, 11, 14),
        total_value=1_000_000_000,
        holdings_count=100,
        top_holdings=[
            {
                "name": "Alphabet Inc",
                "security_class": "CLASS A",
                "value": 80_000_000,
                "percentage": 8.0,
            }
        ],
    )

    # Markdown 表头与分隔线
    assert "| # | 证券 | 市值 (USD) | 占比 |" in msg.content
    assert "| --- | --- | --- | --- |" in msg.content
    # 表格中的条目
    assert "| 1 | Alphabet Inc (CLASS A) | $80,000,000 | 8.00% |" in msg.content


def test_filing_notification_renders_change_categories_as_tables():
    """issue #8：增持/减持等持仓变动应使用表格呈现，并对市值变化高亮。"""
    from datetime import datetime

    changes_summary = {
        "from_quarter": "2024Q2",
        "to_quarter": "2024Q3",
        "total_prev_value": 900_000_000,
        "total_curr_value": 1_000_000_000,
        "total_value_change": 100_000_000,
        "total_percentage_change": 11.11,
        "counts": {"new": 1, "closed": 1, "increased": 1, "decreased": 1},
        "new": [
            {
                "name": "Amazon.com Inc",
                "security_class": "COM",
                "value": 75_000_000,
                "percentage": 7.5,
            }
        ],
        "closed": [
            {"name": "Tesla Inc", "security_class": "COM", "prev_value": 20_000_000}
        ],
        "increased": [
            {
                "name": "Microsoft Corporation",
                "security_class": "COM",
                "prev_value": 90_000_000,
                "curr_value": 120_000_000,
                "value_change": 30_000_000,
                "percentage_change": 33.33,
            }
        ],
        "decreased": [
            {
                "name": "Apple Inc.",
                "security_class": "COM",
                "prev_value": 180_000_000,
                "curr_value": 150_000_000,
                "value_change": -30_000_000,
                "percentage_change": -16.67,
            }
        ],
    }

    msg = NotificationBuilder.build_new_filing_notification(
        fund_name="测试基金",
        cik="0001234567",
        quarter="2024Q3",
        filing_date=datetime(2024, 11, 14),
        total_value=1_000_000_000,
        holdings_count=100,
        changes_summary=changes_summary,
    )

    # 各分类均应渲染为 markdown 表格
    assert "| # | 证券 | 市值 (USD) | 占比 |" in msg.content
    assert "| # | 证券 | 前期市值 (USD) |" in msg.content
    assert "| # | 证券 | 市值变化 (USD) | 占比变化 |" in msg.content

    # 总市值正向变化应使用绿色高亮，减持的负向变化应使用红色高亮
    assert "<font color='green'>+$100,000,000 (+11.11%)</font>" in msg.content
    assert "<font color='red'>-$30,000,000</font>" in msg.content
    # 增持的正向变化也应使用绿色高亮
    assert "<font color='green'>+$30,000,000</font>" in msg.content


def test_filing_notification_escapes_pipe_in_security_name():
    """证券名包含 ``|`` 时应转义，避免破坏 markdown 表格结构。"""
    from datetime import datetime

    msg = NotificationBuilder.build_new_filing_notification(
        fund_name="测试基金",
        cik="0001234567",
        quarter="2024Q3",
        filing_date=datetime(2024, 11, 14),
        total_value=1_000_000_000,
        holdings_count=1,
        top_holdings=[
            {
                "name": "Foo | Bar Corp",
                "security_class": None,
                "value": 10_000_000,
                "percentage": 1.0,
            }
        ],
    )

    # ``|`` 应被转义为 ``\|``
    assert "Foo \\| Bar Corp" in msg.content


def test_feishu_markdown_payload_uses_interactive_card():
    """飞书 payload 应使用 interactive 卡片，并以 lark_md 渲染 Markdown。

    切换为交互式卡片可同时支持表格与 ``<font color>`` 高亮，是 issue #8
    优化的基础。回归测试需保证 schema 稳定。
    """
    notifier = FeishuWebhookNotifier("https://example.com")
    msg = NotificationMessage(
        title="测试",
        content="**重点**: 关注这条消息\n查看 [详情](https://example.com)",
    )

    payload = notifier._build_payload(msg)

    assert payload["msg_type"] == "interactive"
    card = payload["card"]
    assert card["config"]["wide_screen_mode"] is True
    assert card["header"]["title"]["tag"] == "plain_text"
    assert card["header"]["title"]["content"] == "测试"

    elements = card["elements"]
    assert elements, "卡片至少应包含一个元素"
    body = elements[0]
    assert body["tag"] == "div"
    assert body["text"]["tag"] == "lark_md"
    # 原始 Markdown 内容应原样传递给 lark_md（包含 **bold** 与链接）。
    assert "**重点**" in body["text"]["content"]
    assert "[详情](https://example.com)" in body["text"]["content"]


def test_feishu_payload_handles_empty_content():
    """空 content 时应回退到占位文本，避免空 content 字段被飞书拒绝。"""
    notifier = FeishuWebhookNotifier("https://example.com")
    msg = NotificationMessage(title="标题", content="")

    payload = notifier._build_payload(msg)
    body = payload["card"]["elements"][0]
    assert body["text"]["tag"] == "lark_md"
    assert body["text"]["content"], "空内容应回退为非空占位"

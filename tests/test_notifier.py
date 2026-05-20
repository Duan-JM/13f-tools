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


def test_filing_notification_renders_top_holdings_as_native_table():
    """issue #8：主要持仓应使用飞书原生 ``table`` 组件呈现。"""
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

    # 主要持仓应在 elements 中以原生 table 形式存在
    assert msg.elements is not None
    tables = [el for el in msg.elements if el.get("tag") == "table"]
    assert len(tables) == 1
    top_table = tables[0]

    # 列结构
    col_names = [c["display_name"] for c in top_table["columns"]]
    assert col_names == ["#", "证券", "市值 (USD)", "占比"]
    # 数值列右对齐
    aligns = {c["name"]: c["horizontal_align"] for c in top_table["columns"]}
    assert aligns["value"] == "right"
    assert aligns["percentage"] == "right"
    # 证券列使用 lark_md 以支持颜色 / 链接
    data_types = {c["name"]: c["data_type"] for c in top_table["columns"]}
    assert data_types["security"] == "lark_md"

    # 行数据
    assert top_table["rows"] == [
        {
            "idx": "1",
            "security": "Alphabet Inc (CLASS A)",
            "value": "$80,000,000",
            "percentage": "8.00%",
        }
    ]


def test_filing_notification_renders_change_categories_as_native_tables():
    """issue #8：增持/减持等持仓变动应使用原生表格呈现，并对市值变化高亮。"""
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

    assert msg.elements is not None
    tables = [el for el in msg.elements if el.get("tag") == "table"]
    # 没有 top_holdings 时，应有 4 个变动分类表格
    assert len(tables) == 4

    new_table, closed_table, inc_table, dec_table = tables

    # 新增持仓
    assert [c["display_name"] for c in new_table["columns"]] == [
        "#",
        "证券",
        "市值 (USD)",
        "占比",
    ]
    assert new_table["rows"][0]["security"] == "Amazon.com Inc (COM)"

    # 清仓持仓
    assert [c["display_name"] for c in closed_table["columns"]] == [
        "#",
        "证券",
        "前期市值 (USD)",
    ]
    assert closed_table["rows"][0]["prev_value"] == "$20,000,000"

    # 增持持仓：市值变化列用 lark_md，颜色为绿色
    assert [c["display_name"] for c in inc_table["columns"]] == [
        "#",
        "证券",
        "市值变化 (USD)",
        "占比变化",
    ]
    inc_value_change_col = next(
        c for c in inc_table["columns"] if c["name"] == "value_change"
    )
    assert inc_value_change_col["data_type"] == "lark_md"
    assert "<font color='green'>+$30,000,000</font>" in (
        inc_table["rows"][0]["value_change"]
    )
    assert inc_table["rows"][0]["percentage_change"] == "+33.33%"

    # 减持持仓：市值变化列颜色为红色
    assert "<font color='red'>-$30,000,000</font>" in (
        dec_table["rows"][0]["value_change"]
    )

    # 摘要 lark_md 元素应包含总市值变化的颜色高亮
    lark_md_contents = [
        el["text"]["content"]
        for el in msg.elements
        if el.get("tag") == "div" and el.get("text", {}).get("tag") == "lark_md"
    ]
    joined = "\n".join(lark_md_contents)
    assert "<font color='green'>+$100,000,000 (+11.11%)</font>" in joined


def test_filing_notification_preserves_pipe_in_security_name():
    """证券名包含 ``|`` 时不应被转义（飞书原生表格已隔离单元格）。"""
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

    assert msg.elements is not None
    table = next(el for el in msg.elements if el.get("tag") == "table")
    # 不再使用 markdown 表格，``|`` 在单元格中原样保留
    assert table["rows"][0]["security"] == "Foo | Bar Corp"


def test_feishu_payload_uses_card_v2_with_native_body():
    """飞书 payload 应使用 Card 2.0 schema 与 ``body.elements`` 结构。"""
    notifier = FeishuWebhookNotifier("https://example.com")
    msg = NotificationMessage(
        title="测试",
        content="**重点**: 关注这条消息\n查看 [详情](https://example.com)",
    )

    payload = notifier._build_payload(msg)

    assert payload["msg_type"] == "interactive"
    card = payload["card"]
    assert card["schema"] == "2.0"
    assert card["config"]["wide_screen_mode"] is True
    assert card["header"]["title"]["tag"] == "plain_text"
    assert card["header"]["title"]["content"] == "测试"

    body = card["body"]
    assert body["direction"] == "vertical"
    elements = body["elements"]
    assert elements, "卡片至少应包含一个元素"

    first = elements[0]
    assert first["tag"] == "div"
    assert first["text"]["tag"] == "lark_md"
    assert "**重点**" in first["text"]["content"]
    assert "[详情](https://example.com)" in first["text"]["content"]


def test_feishu_payload_uses_message_elements_when_provided():
    """若 ``NotificationMessage.elements`` 提供，应直接作为卡片正文。"""
    notifier = FeishuWebhookNotifier("https://example.com")
    custom_elements = [
        {"tag": "div", "text": {"tag": "lark_md", "content": "Hello"}},
        {
            "tag": "table",
            "columns": [
                {"name": "a", "display_name": "A", "data_type": "text"},
            ],
            "rows": [{"a": "1"}],
        },
    ]
    msg = NotificationMessage(
        title="结构化",
        content="fallback text",
        elements=custom_elements,
    )

    payload = notifier._build_payload(msg)
    body_elements = payload["card"]["body"]["elements"]
    assert body_elements == custom_elements


def test_feishu_payload_handles_empty_content():
    """空 content 且无 elements 时应回退到占位文本。"""
    notifier = FeishuWebhookNotifier("https://example.com")
    msg = NotificationMessage(title="标题", content="")

    payload = notifier._build_payload(msg)
    body = payload["card"]["body"]["elements"][0]
    assert body["text"]["tag"] == "lark_md"
    assert body["text"]["content"], "空内容应回退为非空占位"

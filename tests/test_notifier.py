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


def test_feishu_markdown_parsing():
    """测试飞书 Markdown 解析"""
    notifier = FeishuWebhookNotifier("https://example.com")

    # 测试粗体：飞书自定义机器人不支持 style 字段，
    # 解析结果应为纯 text 节点，且不包含 ``style`` key。
    result = notifier._parse_markdown_to_feishu("普通文本 **粗体文本** 普通文本")
    assert len(result) == 1
    assert len(result[0]) == 3
    for node in result[0]:
        assert node["tag"] == "text"
        assert "style" not in node

    # 测试链接
    result = notifier._parse_markdown_to_feishu("查看 [链接](https://example.com)")
    assert len(result) == 1
    # 应包含文本和链接
    has_link = any(item.get("tag") == "a" for item in result[0])
    assert has_link


def test_feishu_payload_has_no_unsupported_style_field():
    """回归测试：飞书 payload 不应包含 ``style`` 字段，
    否则会触发 ``params error, unknown content value``。"""
    notifier = FeishuWebhookNotifier("https://example.com")
    msg = NotificationMessage(
        title="测试",
        content="**重点**: 关注这条消息\n查看 [详情](https://example.com)",
    )

    payload = notifier._build_payload(msg)
    paragraphs = payload["content"]["post"]["zh_cn"]["content"]

    assert paragraphs, "payload content 不应为空"
    for paragraph in paragraphs:
        for node in paragraph:
            assert "style" not in node, f"节点不应包含 style 字段: {node}"
            assert node["tag"] in {"text", "a", "at", "img"}


def test_feishu_payload_handles_empty_content():
    """空 content 时应回退到占位文本，避免空 content 数组导致 webhook 报错。"""
    notifier = FeishuWebhookNotifier("https://example.com")
    msg = NotificationMessage(title="标题", content="")

    payload = notifier._build_payload(msg)
    paragraphs = payload["content"]["post"]["zh_cn"]["content"]

    assert paragraphs, "空内容应回退为至少一个段落"
    assert paragraphs[0][0]["tag"] == "text"

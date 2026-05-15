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

    # 测试粗体
    result = notifier._parse_markdown_to_feishu("普通文本 **粗体文本** 普通文本")
    assert len(result) == 1
    assert len(result[0]) == 3

    # 测试链接
    result = notifier._parse_markdown_to_feishu("查看 [链接](https://example.com)")
    assert len(result) == 1
    # 应包含文本和链接
    has_link = any(item.get("tag") == "a" for item in result[0])
    assert has_link

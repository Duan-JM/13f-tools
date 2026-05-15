"""
测试监控配置加载器
"""

import tempfile
from pathlib import Path

import pytest

from sec13f_analyzer.monitor_config import MonitorConfigLoader


@pytest.fixture
def sample_config_file():
    """创建临时配置文件"""
    config_content = """
service:
  check_interval: 30
  user_agent: "Test-Agent/1.0"
  state_file: ".test_state.json"

portfolios:
  - name: "测试基金"
    cik: "0001234567"
    enabled: true
    min_report_days: 30

webhooks:
  - name: "测试webhook"
    type: "feishu"
    url: "https://example.com/webhook"
    enabled: true

notification:
  include_holdings_summary: true
  max_holdings_in_summary: 5
  include_report_link: true
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(config_content)
        temp_path = f.name

    yield temp_path

    # 清理
    Path(temp_path).unlink()


def test_load_config(sample_config_file):
    """测试加载配置文件"""
    config = MonitorConfigLoader.load(sample_config_file)

    assert config is not None
    assert config.service.check_interval == 30
    assert config.service.user_agent == "Test-Agent/1.0"
    assert len(config.portfolios) == 1
    assert config.portfolios[0].name == "测试基金"
    assert len(config.webhooks) == 1
    assert config.webhooks[0].type == "feishu"


def test_enabled_portfolios(sample_config_file):
    """测试获取启用的投资组合"""
    config = MonitorConfigLoader.load(sample_config_file)
    enabled = config.enabled_portfolios

    assert len(enabled) == 1
    assert enabled[0].name == "测试基金"


def test_load_nonexistent_file():
    """测试加载不存在的文件"""
    with pytest.raises(FileNotFoundError):
        MonitorConfigLoader.load("nonexistent.yml")


def test_invalid_config():
    """测试无效的配置"""
    invalid_config = """
service:
  check_interval: -1

portfolios: []

webhooks: []

notification: {}
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(invalid_config)
        temp_path = f.name

    try:
        with pytest.raises(ValueError):
            MonitorConfigLoader.load(temp_path)
    finally:
        Path(temp_path).unlink()


def test_config_validation_no_portfolios():
    """测试没有启用投资组合的配置"""
    config_content = """
service:
  check_interval: 30

portfolios:
  - name: "测试基金"
    cik: "0001234567"
    enabled: false

webhooks:
  - name: "测试webhook"
    type: "feishu"
    url: "https://example.com/webhook"
    enabled: true

notification: {}
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(config_content)
        temp_path = f.name

    try:
        with pytest.raises(ValueError, match="至少需要配置一个启用的投资组合"):
            MonitorConfigLoader.load(temp_path)
    finally:
        Path(temp_path).unlink()

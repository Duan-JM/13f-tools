"""
测试配置管理模块
"""

from pathlib import Path

from sec13f_analyzer.config import Config


def test_config_defaults_are_valid(tmp_path, monkeypatch):
    """测试默认配置有效"""
    monkeypatch.chdir(tmp_path)

    config = Config()

    assert config.get_user_agent()
    assert config.validate_config() == []


def test_config_save_and_update(tmp_path):
    """测试配置更新和保存"""
    config_path = tmp_path / "config.ini"
    config = Config()

    config.update_config("MAIN", "company_name", "Test Research")
    config.update_config("MAIN", "email", "test@example.com")
    config.save_config(str(config_path))

    loaded = Config(str(config_path))

    assert loaded.get_company_name() == "Test Research"
    assert loaded.get_email() == "test@example.com"


def test_config_validation_errors(tmp_path):
    """测试无效配置会返回错误"""
    config = Config()

    config.update_config("MAIN", "company_name", "")
    config.update_config("MAIN", "email", "invalid-email")
    config.update_config("MAIN", "request_delay", "0.05")
    config.update_config("MAIN", "max_retries", "11")

    errors = config.validate_config()

    assert "公司名称不能为空" in errors
    assert "邮箱格式不正确" in errors
    assert "请求延迟不能少于0.1秒（SEC要求）" in errors
    assert "重试次数应该在1-10之间" in errors


def test_config_file_lookup(tmp_path, monkeypatch):
    """测试自动查找当前目录配置文件"""
    config_file = tmp_path / "config.ini"
    config_file.write_text(
        "[MAIN]\ncompany_name = Lookup Research\nemail = lookup@example.com\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    config = Config()

    assert Path(config.config_file).name == config_file.name
    assert config.get_company_name() == "Lookup Research"

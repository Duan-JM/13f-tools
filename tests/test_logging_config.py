"""
测试日志配置模块
"""

from unittest.mock import patch

import pytest
from loguru import logger

from sec13f_analyzer.logging_config import (
    DEFAULT_LOG_LEVEL,
    configure_logging,
    resolve_log_level,
)


@pytest.fixture(autouse=True)
def _restore_logger():
    """每个测试后恢复 loguru 的默认 handler"""
    yield
    logger.remove()
    import sys

    logger.add(sys.stderr, level=DEFAULT_LOG_LEVEL)


class TestResolveLogLevel:
    """测试 resolve_log_level 优先级与校验"""

    def test_default_when_env_missing(self, monkeypatch):
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        assert resolve_log_level() == DEFAULT_LOG_LEVEL

    def test_reads_env_variable(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        assert resolve_log_level() == "DEBUG"

    def test_env_is_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "warning")
        assert resolve_log_level() == "WARNING"

    def test_explicit_level_overrides_env(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        assert resolve_log_level("ERROR") == "ERROR"

    def test_invalid_level_falls_back_to_default(self, monkeypatch, capsys):
        monkeypatch.setenv("LOG_LEVEL", "NOPE")
        result = resolve_log_level()
        assert result == DEFAULT_LOG_LEVEL
        captured = capsys.readouterr()
        assert "NOPE" in captured.err
        assert DEFAULT_LOG_LEVEL in captured.err

    def test_whitespace_is_stripped(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "  debug  ")
        assert resolve_log_level() == "DEBUG"

    def test_empty_env_uses_default(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "")
        assert resolve_log_level() == DEFAULT_LOG_LEVEL


class TestConfigureLogging:
    """测试 configure_logging 行为"""

    def test_returns_resolved_level(self, monkeypatch):
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        assert configure_logging() == DEFAULT_LOG_LEVEL

    def test_uses_env_variable(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "WARNING")
        assert configure_logging() == "WARNING"

    def test_explicit_overrides_env(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "INFO")
        assert configure_logging(level="DEBUG") == "DEBUG"

    def test_reconfigures_loguru_handlers(self, monkeypatch):
        """configure_logging 应该移除已有 handler 后重新添加"""
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        with (
            patch.object(logger, "remove") as mock_remove,
            patch.object(logger, "add") as mock_add,
        ):
            configure_logging(level="ERROR")
            mock_remove.assert_called_once()
            mock_add.assert_called_once()
            # level 关键字参数应被传给 logger.add
            assert mock_add.call_args.kwargs.get("level") == "ERROR"

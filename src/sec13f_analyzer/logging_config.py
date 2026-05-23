"""
日志配置

提供基于环境变量的日志等级配置功能。

支持的环境变量:
    - ``LOG_LEVEL``: 日志等级，可选值为 loguru 支持的标准等级
      （``TRACE``、``DEBUG``、``INFO``、``SUCCESS``、``WARNING``、``ERROR``、
      ``CRITICAL``），大小写不敏感。未设置时默认为 ``INFO``。

优先级（高 -> 低）:
    1. 显式传入 ``configure_logging(level=...)`` 的参数
    2. ``LOG_LEVEL`` 环境变量
    3. 默认值 ``INFO``
"""

import os
import sys
from typing import Optional

from loguru import logger

DEFAULT_LOG_LEVEL = "INFO"
_VALID_LEVELS = {
    "TRACE",
    "DEBUG",
    "INFO",
    "SUCCESS",
    "WARNING",
    "ERROR",
    "CRITICAL",
}


def resolve_log_level(level: Optional[str] = None) -> str:
    """解析日志等级

    按优先级返回有效的 loguru 日志等级名称。

    Args:
        level: 显式指定的日志等级。优先级最高。

    Returns:
        规范化的（大写的）日志等级名称。若解析到的等级无效，
        则回退到 :data:`DEFAULT_LOG_LEVEL` 并打印一条警告到 stderr。
    """
    raw = level if level is not None else os.environ.get("LOG_LEVEL")
    if not raw:
        return DEFAULT_LOG_LEVEL

    normalized = raw.strip().upper()
    if normalized not in _VALID_LEVELS:
        sys.stderr.write(
            f"[sec13f-analyzer] 警告: 未知的 LOG_LEVEL '{raw}'，"
            f"回退到 {DEFAULT_LOG_LEVEL}。"
            f"可选值: {', '.join(sorted(_VALID_LEVELS))}\n"
        )
        return DEFAULT_LOG_LEVEL
    return normalized


def configure_logging(level: Optional[str] = None) -> str:
    """配置 loguru 日志输出

    移除现有的 loguru handler 并重新添加一个写入 stderr 的 handler，
    日志等级按 :func:`resolve_log_level` 的规则解析。

    Args:
        level: 显式指定的日志等级。若为 ``None``，则读取 ``LOG_LEVEL``
            环境变量；若环境变量也未设置，则使用 ``INFO``。

    Returns:
        最终生效的日志等级名称。
    """
    effective = resolve_log_level(level)
    logger.remove()
    logger.add(sys.stderr, level=effective)
    return effective

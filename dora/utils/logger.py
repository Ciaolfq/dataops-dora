"""
日志工具模块
提供统一的日志配置和全局 logger 实例
"""

import logging
import sys
from typing import Optional

from config.config_loader import global_cfg


def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """
    获取配置好的 logger 实例

    Args:
        name: logger 名称
        level: 日志级别，为 None 时从配置读取

    Returns:
        配置好的 Logger 实例
    """
    # 从配置获取日志级别
    if level is None:
        log_cfg = global_cfg.get("log", {})
        level = log_cfg.get("level", "INFO")

    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    log_level = level_map.get(level.upper(), logging.INFO)

    # 获取或创建 logger
    logger = logging.getLogger(name)

    # 如果 logger 已经配置过处理器，直接返回
    if logger.handlers:
        logger.setLevel(log_level)
        return logger

    logger.setLevel(log_level)

    # 日志格式
    log_cfg = global_cfg.get("log", {})
    fmt_str = log_cfg.get(
        "format",
        "[%(asctime)s] %(levelname)s | %(name)s: %(message)s"
    )
    fmt = logging.Formatter(fmt_str)

    # 控制台输出处理器
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    sh.setLevel(log_level)
    logger.addHandler(sh)

    # 禁止向上传播，避免重复输出
    logger.propagate = False

    return logger


# 全局 DORA logger 实例
logger = get_logger("DORA")

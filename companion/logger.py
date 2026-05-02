"""Companion 日志配置 — 文件日志 + 控制台错误输出。

用法：
    from companion.logger import setup_logger, get_logger

    # 在程序入口调用一次
    setup_logger(level="INFO", log_file="workspace/companion/companion.log")

    # 在模块中使用
    logger = get_logger(__name__)
    logger.info("模块初始化完成")
"""

import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logger(
    level: str = "INFO",
    log_file: Optional[str] = None,
    format_str: Optional[str] = None,
) -> None:
    """配置根 logger 和 companion logger。

    Args:
        level: 日志级别（DEBUG/INFO/WARNING/ERROR）
        log_file: 日志文件路径，None 则不写文件
        format_str: 自定义格式，None 则使用默认
    """
    if format_str is None:
        format_str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 清除已有 handlers（避免重复）
    root.handlers.clear()

    # 控制台 handler — 只输出 WARNING 及以上
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.WARNING)
    console.setFormatter(logging.Formatter(format_str))
    root.addHandler(console)

    # 文件 handler — 输出所有级别
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(format_str))
        root.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的 logger。"""
    return logging.getLogger(name)

"""Logging configuration for the trading bot."""

import logging
import os
from logging.handlers import RotatingFileHandler

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")


def setup_logger(name: str, log_file: str, level: int = logging.DEBUG) -> logging.Logger:
    """Create a logger with a rotating file handler and a console handler."""
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def get_market_logger() -> logging.Logger:
    return setup_logger("market_orders", os.path.join(LOGS_DIR, "market_order.log"))


def get_limit_logger() -> logging.Logger:
    return setup_logger("limit_orders", os.path.join(LOGS_DIR, "limit_order.log"))


def get_stop_limit_logger() -> logging.Logger:
    return setup_logger("stop_limit_orders", os.path.join(LOGS_DIR, "stop_limit_order.log"))


def get_general_logger() -> logging.Logger:
    return setup_logger("trading_bot", os.path.join(LOGS_DIR, "trading_bot.log"))

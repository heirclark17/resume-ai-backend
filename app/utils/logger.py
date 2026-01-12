import logging
import sys
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler


def setup_logger(name: str = "resume_ai", level: str = "INFO") -> logging.Logger:
    """
    Setup application logger with console and file handlers

    Args:
        name: Logger name
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Don't add handlers if they already exist
    if logger.handlers:
        return logger

    # Set log level
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(log_level)

    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    logger.addHandler(console_handler)

    # Rotating file handler (prevents disk space issues)
    # Rotates when log reaches 10MB, keeps 5 backup files
    try:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        log_file = log_dir / "resume_ai.log"
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB per file
            backupCount=5,  # Keep 5 backup files (total: 50MB max)
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        # If file logging fails (e.g., Railway read-only filesystem), continue with console only
        logger.warning(f"Could not setup file logging: {e}")

    return logger


# Create default logger instance
logger = setup_logger()


def get_logger(name: str = None) -> logging.Logger:
    """
    Get logger instance

    Args:
        name: Optional logger name (defaults to main logger)

    Returns:
        Logger instance
    """
    if name:
        return setup_logger(name)
    return logger


# Convenience functions
def debug(msg: str, *args, **kwargs):
    """Log debug message"""
    logger.debug(msg, *args, **kwargs)


def info(msg: str, *args, **kwargs):
    """Log info message"""
    logger.info(msg, *args, **kwargs)


def warning(msg: str, *args, **kwargs):
    """Log warning message"""
    logger.warning(msg, *args, **kwargs)


def error(msg: str, *args, **kwargs):
    """Log error message"""
    logger.error(msg, *args, **kwargs)


def critical(msg: str, *args, **kwargs):
    """Log critical message"""
    logger.critical(msg, *args, **kwargs)

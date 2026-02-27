import logging
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler


class StructuredFormatter(logging.Formatter):
    """JSON structured log formatter with correlation ID injection"""

    def format(self, record: logging.LogRecord) -> str:
        # Build structured log entry
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }

        # Add correlation ID and user ID from extra (set by correlation middleware)
        if hasattr(record, "correlation_id") and record.correlation_id:
            entry["correlation_id"] = record.correlation_id
        if hasattr(record, "user_id") and record.user_id:
            entry["user_id"] = record.user_id

        # Add any extra fields passed via logger.info("msg", extra={...})
        for key in ("method", "path", "status", "duration_ms", "client_ip",
                     "error", "error_type", "service", "circuit_state"):
            if hasattr(record, key):
                entry[key] = getattr(record, key)

        # Add source location for errors
        if record.levelno >= logging.WARNING:
            entry["source"] = f"{record.filename}:{record.lineno}"

        # Add exception info if present
        if record.exc_info and record.exc_info[1]:
            entry["exception"] = {
                "type": type(record.exc_info[1]).__name__,
                "message": str(record.exc_info[1]),
            }

        return json.dumps(entry, default=str)


class SimpleFormatter(logging.Formatter):
    """Human-readable formatter for local development"""

    def __init__(self):
        super().__init__(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )


def setup_logger(name: str = "resume_ai", level: str = "INFO") -> logging.Logger:
    """
    Setup application logger with structured JSON output.

    In production (Railway), outputs JSON to stdout for log drain ingestion.
    Optionally writes to file for local development.
    """
    logger = logging.getLogger(name)

    # Don't add handlers if they already exist
    if logger.handlers:
        return logger

    # Set log level
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(log_level)

    # Determine if we should use structured JSON (production) or simple (dev)
    import os
    is_production = bool(os.getenv("RAILWAY_ENVIRONMENT")) or os.getenv("LOG_FORMAT") == "json"

    # Console handler (stdout) - always present
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    if is_production:
        console_handler.setFormatter(StructuredFormatter())
    else:
        console_handler.setFormatter(SimpleFormatter())

    logger.addHandler(console_handler)

    # Rotating file handler for local development only
    if not is_production:
        try:
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)

            log_file = log_dir / "resume_ai.log"
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(StructuredFormatter())
            logger.addHandler(file_handler)
        except Exception as e:
            # Railway has read-only filesystem
            logger.warning(f"Could not setup file logging: {e}")

    return logger


# Create default logger instance
logger = setup_logger()


def get_logger(name: str = None) -> logging.Logger:
    """Get logger instance"""
    if name:
        return setup_logger(name)
    return logger


# Convenience functions
def debug(msg: str, *args, **kwargs):
    logger.debug(msg, *args, **kwargs)


def info(msg: str, *args, **kwargs):
    logger.info(msg, *args, **kwargs)


def warning(msg: str, *args, **kwargs):
    logger.warning(msg, *args, **kwargs)


def error(msg: str, *args, **kwargs):
    logger.error(msg, *args, **kwargs)


def critical(msg: str, *args, **kwargs):
    logger.critical(msg, *args, **kwargs)

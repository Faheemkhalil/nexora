"""Structured logging using loguru.

API keys, passwords, tokens, and private credentials are never logged.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from loguru import logger


SENSITIVE_PATTERNS: list[tuple[str, str]] = [
    (r"sk-[A-Za-z0-9_-]{20,}", "sk-***REDACTED***"),
    (r"Bearer\s+[A-Za-z0-9._-]+", "Bearer ***REDACTED***"),
    (r"password['\"]?\s*[:=]\s*['\"][^'\"]+['\"]", "password=***REDACTED***"),
    (r"password['\"]?\s*[:=]\s*[A-Za-z0-9._-]+", "password=***REDACTED***"),
    (r"api[_-]?key['\"]?\s*[:=]\s*['\"][^'\"]+['\"]", "api_key=***REDACTED***"),
    (r"api[_-]?key['\"]?\s*[:=]\s*[A-Za-z0-9._-]+", "api_key=***REDACTED***"),
]


def _redact(message: str) -> str:
    for pattern, replacement in SENSITIVE_PATTERNS:
        message = re.sub(pattern, replacement, message, flags=re.IGNORECASE)
    return message


class _RedactingSink:
    """Sink that redacts sensitive information before writing."""

    def __init__(self, sink):
        self._sink = sink

    def write(self, message):
        record = message.record
        record["message"] = _redact(record["message"])
        for key, value in record["extra"].items():
            if isinstance(value, str):
                record["extra"][key] = _redact(value)
        # Write the formatted message string to the underlying sink
        self._sink.write(str(message))


def configure_logging(log_level: str = "INFO") -> None:
    """Configure loguru with structured output and redaction."""
    logger.remove()

    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</> | "
        "<level>{level: <8}</> | "
        "<cyan>{name}</>:<cyan>{function}</>:<cyan>{line}</> | "
        "{message}"
    )

    logger.add(
        _RedactingSink(sys.stderr),
        level=log_level,
        format=log_format,
        colorize=True,
    )

    # Use project-relative log path since home may be read-only
    log_path = Path(__file__).parent.parent.parent / "data" / "logs" / "nexora.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Open file in append mode for loguru
    log_file = open(log_path, "a", encoding="utf-8")

    logger.add(
        _RedactingSink(log_file),
        level="DEBUG",
        format=log_format,
        colorize=False,
    )


configure_logging()

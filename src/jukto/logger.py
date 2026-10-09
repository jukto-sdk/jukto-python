"""Logging configuration and utilities for Jukto SDK."""

from __future__ import annotations

import logging
from typing import Any

# Root logger for Jukto SDK
logger = logging.getLogger("jukto")

# Default to NullHandler to avoid "No handler found" warnings when imported
logger.addHandler(logging.NullHandler())


def enable_debug_logging(level: int = logging.DEBUG) -> logging.Handler:
    """Convenience helper to attach a formatted StreamHandler to the Jukto logger.

    Adapter diagnostics contain metadata only, never request/response payloads.
    This configures the jukto logger, not third-party loggers such as httpx.
    """
    logger.setLevel(level)

    # Check if a StreamHandler already exists
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.NullHandler):
            handler.setLevel(level)
            return handler

    handler = logging.StreamHandler()
    handler.setLevel(level)
    formatter = logging.Formatter(
        "[%(asctime)s] [jukto] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return handler


def mask_sensitive(data: Any) -> Any:
    """Fully redact known credential values; this is not a general payload sanitizer."""
    sensitive_keys = {
        "api_key",
        "secret_key",
        "client_secret",
        "password",
        "token",
        "access_token",
        "refresh_token",
        "api-key",
        "secret-key",
        "authorization",
        "x-api-key",
        "apikey",
        "store_passwd",
        "private_key",
    }
    if isinstance(data, dict):
        masked: dict[str, Any] = {}
        for k, v in data.items():
            if str(k).lower() in sensitive_keys:
                masked[k] = "***"
            elif isinstance(v, (dict, list)):
                masked[k] = mask_sensitive(v)
            else:
                masked[k] = v
        return masked
    elif isinstance(data, list):
        return [mask_sensitive(item) for item in data]
    return data

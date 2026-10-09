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

    Useful for development and debugging third-party API interactions.
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
    """Mask sensitive keys (passwords, tokens, secret keys) in log payloads."""
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
    }
    if isinstance(data, dict):
        masked: dict[str, Any] = {}
        for k, v in data.items():
            if str(k).lower() in sensitive_keys and isinstance(v, str):
                masked[k] = f"{v[:3]}...{v[-3:]}" if len(v) > 6 else "***"
            elif isinstance(v, (dict, list)):
                masked[k] = mask_sensitive(v)
            else:
                masked[k] = v
        return masked
    elif isinstance(data, list):
        return [mask_sensitive(item) for item in data]
    return data

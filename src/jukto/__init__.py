"""Jukto - A unified Python SDK for Bangladesh's digital ecosystem (Logistics, SMS, Payments)."""

from __future__ import annotations

from jukto.exceptions import (
    InsufficientBalanceError,
    InvalidRequestError,
    JuktoConfigurationError,
    JuktoError,
    JuktoValidationError,
    ProviderAuthenticationError,
    ProviderConnectionError,
    ProviderError,
    ProviderRateLimitError,
    ProviderServerError,
    ProviderTimeoutError,
    ResourceNotFoundError,
)
from jukto.interfaces.logistics import BaseLogisticsProvider, Parcel
from jukto.interfaces.sms import BaseSMSProvider
from jukto.logger import enable_debug_logging, logger
from jukto.providers.logistics.pathao import PathaoClient
from jukto.providers.logistics.steadfast import SteadfastClient
from jukto.providers.sms.alphasms import AlphaSMSClient
from jukto.providers.sms.greenweb import GreenWebClient

__all__ = [
    # Domain Interfaces & Models
    "BaseLogisticsProvider",
    "BaseSMSProvider",
    "Parcel",
    # Logistics Providers
    "SteadfastClient",
    "PathaoClient",
    # SMS Providers
    "GreenWebClient",
    "AlphaSMSClient",
    # Exceptions
    "JuktoError",
    "JuktoValidationError",
    "JuktoConfigurationError",
    "ProviderError",
    "ProviderAuthenticationError",
    "ProviderConnectionError",
    "ProviderTimeoutError",
    "ProviderRateLimitError",
    "ProviderServerError",
    "InvalidRequestError",
    "ResourceNotFoundError",
    "InsufficientBalanceError",
    # Logging
    "logger",
    "enable_debug_logging",
]

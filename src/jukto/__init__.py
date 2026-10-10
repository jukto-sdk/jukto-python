"""Jukto - A unified Python SDK for Bangladesh's digital ecosystem (Logistics, SMS, Payments)."""

from __future__ import annotations

from jukto.exceptions import (
    InsufficientBalanceError,
    UnexpectedProviderResponseError,
    SMSBatchError,
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
from jukto.results import SMSBatchResult, Outcome, ShipmentCreationResult, ShipmentStatusResult, SMSRecipientResult, SMSSubmissionResult
from jukto.options import PathaoOptions, RedXOptions, ProviderCapabilities
from jukto.logger import enable_debug_logging, logger
from jukto.providers.logistics.pathao import PathaoClient
from jukto.providers.logistics.redx import RedXClient
from jukto.providers.logistics.steadfast import SteadfastClient
from jukto.providers.sms.alphasms import AlphaSMSClient
from jukto.providers.sms.bulksmsbd import BulkSMSBDClient
from jukto.providers.sms.greenweb import GreenWebClient

__all__ = [
    # Domain Interfaces & Models
    "BaseLogisticsProvider",
    "BaseSMSProvider",
    "Parcel",
    "Outcome", "ShipmentCreationResult", "ShipmentStatusResult",
    "SMSRecipientResult", "SMSSubmissionResult", "PathaoOptions", "RedXOptions", "ProviderCapabilities",
    # Logistics Providers
    "SteadfastClient",
    "PathaoClient",
    "RedXClient",
    # SMS Providers
    "GreenWebClient",
    "AlphaSMSClient",
    "BulkSMSBDClient",
    # Exceptions
    "JuktoError",
    "UnexpectedProviderResponseError",
    "SMSBatchError",
    "SMSBatchResult",
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

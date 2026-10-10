"""Custom exception hierarchy for Jukto SDK.

Normalized exceptions for recognized SDK and logistics/SMS provider failures.
Unknown provider codes remain generic; internal programming errors can escape.
"""

from __future__ import annotations

from typing import Any, Optional
from jukto.results import Outcome, SMSSubmissionResult


class JuktoError(Exception):
    """Base exception for all Jukto SDK errors.

    All exceptions raised by Jukto inherit from this class, allowing developers
    to catch all SDK errors with a single `except JuktoError:` block.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        response_body: Optional[Any] = None,
        provider: Optional[str] = None,
        http_status: Optional[int] = None,
        provider_error_code: Optional[int | str] = None,
        request_id: Optional[str] = None,
        retry_after: Optional[str] = None,
        outcome: Outcome = Outcome.UNKNOWN,
        reconciliation_required: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_body = response_body
        self.provider = provider
        self.http_status = http_status
        self.provider_error_code = provider_error_code
        self.request_id = request_id
        self.retry_after = retry_after
        self.outcome = outcome
        self.reconciliation_required = reconciliation_required

    def __str__(self) -> str:
        parts: list[str] = [self.message]
        details: list[str] = []
        if self.provider:
            details.append(f"provider={self.provider}")
        if self.status_code is not None:
            details.append(f"status_code={self.status_code}")
        if details:
            parts.append(f"({', '.join(details)})")
        return " ".join(parts)

    def __repr__(self) -> str:
        parts = [f"message={self.message!r}"]
        if self.provider:
            parts.append(f"provider={self.provider!r}")
        if self.status_code is not None:
            parts.append(f"status_code={self.status_code}")
        return f"{self.__class__.__name__}({', '.join(parts)})"


class JuktoValidationError(JuktoError):
    """Raised when client-side validation fails before sending a request.

    Examples:
        - Empty required shipment phone string (no numbering-plan validation)
        - Missing required parcel or order fields
        - Negative COD amount
    """

    pass


class JuktoConfigurationError(JuktoError):
    """Raised when SDK configuration or credentials are missing or invalid.

    Examples:
        - API key or secret not provided
        - Unsupported provider configuration
    """

    pass


class ProviderError(JuktoError):
    """Base exception for errors returned by upstream third-party service providers."""

    pass


class ProviderAuthenticationError(ProviderError):
    """Raised when provider rejects credentials (e.g. HTTP 401/403 or invalid token)."""

    pass


class ProviderConnectionError(ProviderError):
    """Raised when a network failure prevents reaching the provider."""

    pass


class ProviderTimeoutError(ProviderConnectionError):
    """Raised when a request to a provider times out."""

    pass


class ProviderRateLimitError(ProviderError):
    """Raised when an API rate limit is exceeded (e.g. HTTP 429)."""

    pass


class ProviderServerError(ProviderError):
    """Raised when an upstream provider fails with a 5xx server error."""

    pass


class InvalidRequestError(ProviderError):
    """Raised when provider rejects request due to invalid parameters (e.g. HTTP 400/422)."""

    pass


class ResourceNotFoundError(ProviderError):
    """Raised when a requested resource (consignment ID, order, etc.) is not found (e.g. HTTP 404)."""

    pass


class InsufficientBalanceError(ProviderError):
    """Raised when account balance or credits are depleted."""

    pass


class UnexpectedProviderResponseError(ProviderError):
    """Upstream decoding/schema failure; a side effect may already have happened."""


class SMSBatchError(ProviderError):
    """Batch contains failed or unknown entries; inspect results before retrying."""

    def __init__(self, message: str, *, results: Any, **kwargs: Any) -> None:
        super().__init__(message, **kwargs)
        self.results = results
        self.normalized_result: Optional[SMSSubmissionResult] = None

"""Adapter for AlphaSMS (sms.net.bd) SMS Gateway."""

from __future__ import annotations

from typing import Any, Optional
import httpx

from jukto.exceptions import (
    InsufficientBalanceError,
    InvalidRequestError,
    ProviderAuthenticationError,
    ProviderConnectionError,
    ProviderError,
    ProviderRateLimitError,
    ProviderServerError,
    ProviderTimeoutError,
    ResourceNotFoundError,
)
from jukto.interfaces.sms import BaseSMSProvider
from jukto.logger import logger, mask_sensitive


class AlphaSMSClient(BaseSMSProvider):
    """Adapter for AlphaSMS (sms.net.bd) API."""

    DEFAULT_URL = "https://api.sms.net.bd/sendsms"

    def __init__(
        self,
        api_key: str,
        sender_id: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
    ) -> None:
        super().__init__(
            api_key=api_key,
            sender_id=sender_id,
            base_url=base_url or self.DEFAULT_URL,
            timeout=timeout,
        )

    def _handle_http_status_error(self, exc: httpx.HTTPStatusError) -> None:
        status_code = exc.response.status_code
        text = exc.response.text.strip()
        error_message = f"AlphaSMS API error ({status_code}): {text or exc.response.reason_phrase}"
        logger.error("AlphaSMS HTTP status error [%d]: %s", status_code, text)

        if status_code in (401, 403):
            raise ProviderAuthenticationError(
                error_message,
                status_code=status_code,
                response_body=text,
                provider="AlphaSMS",
            ) from exc
        elif status_code == 429:
            raise ProviderRateLimitError(
                error_message,
                status_code=status_code,
                response_body=text,
                provider="AlphaSMS",
            ) from exc
        elif status_code in (400, 422):
            raise InvalidRequestError(
                error_message,
                status_code=status_code,
                response_body=text,
                provider="AlphaSMS",
            ) from exc
        elif status_code >= 500:
            raise ProviderServerError(
                error_message,
                status_code=status_code,
                response_body=text,
                provider="AlphaSMS",
            ) from exc
        else:
            raise ProviderError(
                error_message,
                status_code=status_code,
                response_body=text,
                provider="AlphaSMS",
            ) from exc

    def _inspect_response_data(self, data: Any, response: httpx.Response) -> dict[str, Any]:
        """Classify documented codes; provenance: tests/fixtures/alphasms_contract.json."""
        raw_code = data.get("error") if isinstance(data, dict) else None
        # The official JSON example uses integers; its C# examples use string codes.
        # Accept canonical decimal strings only, not bools, floats or coercible objects.
        if type(raw_code) is int:
            error_code = raw_code
        elif isinstance(raw_code, str) and raw_code.isascii() and raw_code.isdecimal() and str(int(raw_code)) == raw_code:
            error_code = int(raw_code)
        else:
            raise ProviderError(
                "AlphaSMS returned an unrecognized error-code structure",
                status_code=response.status_code,
                response_body=data,
                provider="AlphaSMS",
            )

        if error_code == 0:
            return data

        # Jukto categories derived from https://sms.bd/api (checked 2026-10-10).
        # 403 includes permission denial; expired accounts need account remediation.
        error_types = {
            400: InvalidRequestError,
            403: ProviderAuthenticationError,
            404: ResourceNotFoundError,
            405: ProviderAuthenticationError,
            409: ProviderServerError,
            410: ProviderAuthenticationError,
            411: ProviderAuthenticationError,
            412: InvalidRequestError,
            413: InvalidRequestError,
            414: InvalidRequestError,
            415: InvalidRequestError,
            416: InvalidRequestError,
            417: InsufficientBalanceError,
            420: InvalidRequestError,
        }
        msg = data.get("msg") or data.get("message") or "AlphaSMS error"
        error_message = f"AlphaSMS error ({error_code}): {msg}"
        logger.error("AlphaSMS API returned error: %s", error_message)
        raise error_types.get(error_code, ProviderError)(
            error_message,
            status_code=error_code,
            response_body=data,
            provider="AlphaSMS",
        )

    def send_sms(self, phone_numbers: str | list[str], message: str) -> dict[str, Any]:
        if isinstance(phone_numbers, list):
            to_string = ",".join(phone_numbers)
        else:
            to_string = phone_numbers

        payload = {
            "api_key": self.api_key,
            "msg": message,
            "to": to_string,
        }
        if self.sender_id:
            payload["sender_id"] = self.sender_id

        masked = mask_sensitive(payload)
        logger.debug("AlphaSMS request to %s | payload: %s", self.base_url, masked)

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(self.base_url, data=payload)
                logger.debug("AlphaSMS HTTP status: %d", response.status_code)
                response.raise_for_status()
                data = response.json()
                return self._inspect_response_data(data, response)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                f"AlphaSMS request timed out: {exc}",
                provider="AlphaSMS",
            ) from exc
        except httpx.HTTPStatusError as exc:
            self._handle_http_status_error(exc)
            raise
        except httpx.RequestError as exc:
            raise ProviderConnectionError(
                f"Failed to connect to AlphaSMS: {exc}",
                provider="AlphaSMS",
            ) from exc

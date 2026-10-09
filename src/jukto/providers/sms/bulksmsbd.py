"""Adapter for BulkSMSBD (bulksmsbd.net) SMS Gateway."""

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
)
from jukto.interfaces.sms import BaseSMSProvider
from jukto.logger import logger, mask_sensitive


class BulkSMSBDClient(BaseSMSProvider):
    """Adapter for BulkSMSBD (bulksmsbd.net) API."""

    DEFAULT_URL = "http://bulksmsbd.net/api/smsapi"

    def __init__(
        self,
        api_key: str,
        sender_id: str,
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
        error_message = f"BulkSMSBD API error ({status_code}): {text or exc.response.reason_phrase}"
        logger.error("BulkSMSBD HTTP error [%d]: %s", status_code, text)

        if status_code in (401, 403):
            raise ProviderAuthenticationError(
                error_message,
                status_code=status_code,
                response_body=text,
                provider="BulkSMSBD",
            ) from exc
        elif status_code == 429:
            raise ProviderRateLimitError(
                error_message,
                status_code=status_code,
                response_body=text,
                provider="BulkSMSBD",
            ) from exc
        elif status_code in (400, 422):
            raise InvalidRequestError(
                error_message,
                status_code=status_code,
                response_body=text,
                provider="BulkSMSBD",
            ) from exc
        elif status_code >= 500:
            raise ProviderServerError(
                error_message,
                status_code=status_code,
                response_body=text,
                provider="BulkSMSBD",
            ) from exc
        else:
            raise ProviderError(
                error_message,
                status_code=status_code,
                response_body=text,
                provider="BulkSMSBD",
            ) from exc

    def _inspect_response_data(self, data: Any, response: httpx.Response) -> dict[str, Any]:
        """Inspect BulkSMSBD response code and payload."""
        if not isinstance(data, dict):
            return {"data": data}

        response_code = data.get("response_code")
        error_message_text = data.get("error_message") or data.get("message") or "BulkSMSBD error"

        # BulkSMSBD Success is usually 202
        if response_code not in (None, 202):
            error_message = f"BulkSMSBD error ({response_code}): {error_message_text}"
            logger.error("BulkSMSBD returned error: %s", error_message)

            if response_code in (1002, 1007):  # 1002: Invalid API Key, 1007: Balance low/unauthorized
                if "balance" in error_message_text.lower():
                    raise InsufficientBalanceError(
                        error_message,
                        status_code=response_code,
                        response_body=data,
                        provider="BulkSMSBD",
                    )
                raise ProviderAuthenticationError(
                    error_message,
                    status_code=response_code,
                    response_body=data,
                    provider="BulkSMSBD",
                )
            elif response_code in (1003, 1004, 1008):  # 1003: Insufficient balance, 1008: Low balance
                raise InsufficientBalanceError(
                    error_message,
                    status_code=response_code,
                    response_body=data,
                    provider="BulkSMSBD",
                )
            elif response_code in (1005, 1006, 1010):  # Invalid number, sender id, message format
                raise InvalidRequestError(
                    error_message,
                    status_code=response_code,
                    response_body=data,
                    provider="BulkSMSBD",
                )
            else:
                raise ProviderError(
                    error_message,
                    status_code=response_code,
                    response_body=data,
                    provider="BulkSMSBD",
                )

        return data

    def send_sms(self, phone_numbers: str | list[str], message: str) -> dict[str, Any]:
        if isinstance(phone_numbers, list):
            to_string = ",".join(phone_numbers)
        else:
            to_string = phone_numbers

        payload = {
            "api_key": self.api_key,
            "type": "text",
            "number": to_string,
            "senderid": self.sender_id or "",
            "message": message,
        }

        masked = mask_sensitive(payload)
        logger.debug("BulkSMSBD request to %s | payload: %s", self.base_url, masked)

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(self.base_url, data=payload)
                logger.debug("BulkSMSBD HTTP status: %d", response.status_code)
                response.raise_for_status()
                data = response.json()
                return self._inspect_response_data(data, response)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                f"BulkSMSBD request timed out: {exc}",
                provider="BulkSMSBD",
            ) from exc
        except httpx.HTTPStatusError as exc:
            self._handle_http_status_error(exc)
            raise
        except httpx.RequestError as exc:
            raise ProviderConnectionError(
                f"Failed to connect to BulkSMSBD: {exc}",
                provider="BulkSMSBD",
            ) from exc

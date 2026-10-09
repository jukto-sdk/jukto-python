"""Adapter for BulkSMSBD (bulksmsbd.net) SMS Gateway."""

from __future__ import annotations

from typing import Any, Optional
import httpx
from jukto._responses import decode_json, unexpected
from jukto._transport import secure_http_client

from jukto.exceptions import (
    InvalidRequestError,
    ProviderAuthenticationError,
    ProviderConnectionError,
    ProviderError,
    ProviderRateLimitError,
    ProviderServerError,
    ProviderTimeoutError,
)
from jukto.interfaces.sms import BaseSMSProvider
from jukto.logger import logger


class BulkSMSBDClient(BaseSMSProvider):
    """Adapter for BulkSMSBD (bulksmsbd.net) API."""

    DEFAULT_URL = "http://bulksmsbd.net/api/smsapi"

    def __init__(
        self,
        api_key: str,
        sender_id: str,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
        *,
        allow_insecure_http: bool = False,
    ) -> None:
        super().__init__(
            api_key=api_key,
            sender_id=sender_id,
            base_url=base_url or self.DEFAULT_URL,
            timeout=timeout,
            allow_insecure_http=allow_insecure_http,
        )

    def _handle_http_status_error(self, exc: httpx.HTTPStatusError) -> None:
        status_code = exc.response.status_code
        text = exc.response.text.strip()
        error_message = f'BulkSMSBD API error ({status_code}): [details withheld]'
        logger.error('provider=BulkSMSBD operation=handle_http_status_error event=error status=%d', status_code)

        if status_code in (401, 403):
            raise ProviderAuthenticationError(
                error_message,
                status_code=status_code,
                response_body=text,
                provider="BulkSMSBD",
            ) from None
        elif status_code == 429:
            raise ProviderRateLimitError(
                error_message,
                status_code=status_code,
                response_body=text,
                provider="BulkSMSBD",
            ) from None
        elif status_code in (400, 422):
            raise InvalidRequestError(
                error_message,
                status_code=status_code,
                response_body=text,
                provider="BulkSMSBD",
            ) from None
        elif status_code >= 500:
            raise ProviderServerError(
                error_message,
                status_code=status_code,
                response_body=text,
                provider="BulkSMSBD",
            ) from None
        else:
            raise ProviderError(
                error_message,
                status_code=status_code,
                response_body=text,
                provider="BulkSMSBD",
            ) from None

    def _inspect_response_data(self, data: Any, response: httpx.Response) -> dict[str, Any]:
        """Preserve codes without assigning unverified provider-specific meanings.

        See docs/provider-contracts.md for the unresolved official contract.
        """
        response_code = data.get("response_code") if isinstance(data, dict) else None
        if type(response_code) is not int:
            raise unexpected(response, "BulkSMSBD", data)

        # Legacy compatibility only: 202 has not been independently verified.
        # Do not infer string/float variants or error meanings from existing mocks.
        if response_code == 202:
            return data

        message = data.get("error_message") or data.get("message") or "Unclassified provider error"
        raise ProviderError(
            f'BulkSMSBD error ({response_code}): [details withheld]',
            status_code=response_code,
            response_body=data,
            provider="BulkSMSBD",
        )

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


        logger.debug('provider=BulkSMSBD operation=send_sms event=request')

        try:
            with secure_http_client(self.base_url, self.timeout, self.allow_insecure_http) as client:
                response = client.post(self.base_url, data=payload)
                logger.debug('provider=BulkSMSBD operation=send_sms event=response status=%d', response.status_code)
                response.raise_for_status()
                data = decode_json(response, "BulkSMSBD")
                return self._inspect_response_data(data, response)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                'BulkSMSBD request timed out: [details withheld]',
                provider="BulkSMSBD",
            ) from None
        except httpx.HTTPStatusError as exc:
            self._handle_http_status_error(exc)
            raise
        except httpx.RequestError as exc:
            raise ProviderConnectionError(
                'Failed to connect to BulkSMSBD: [details withheld]',
                provider="BulkSMSBD",
            ) from None

"""Adapter for BulkSMSBD (bulksmsbd.net) SMS Gateway."""

from __future__ import annotations

from typing import Any, NoReturn
import httpx
from jukto._responses import unexpected

from jukto.exceptions import InvalidRequestError, ProviderAuthenticationError, ProviderError, ProviderRateLimitError, ProviderServerError
from jukto.logger import logger


class BulkSMSBDContract:
    api_key: str
    base_url: str | None
    sender_id: str | None

    def _handle_http_status_error(self, exc: httpx.HTTPStatusError) -> NoReturn:
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


    def _prepare_sms(self, phone_numbers: str | list[str], message: str) -> dict[str, Any]:
        if isinstance(phone_numbers, list):
            to_string = ",".join(phone_numbers)
        else:
            to_string = phone_numbers

        assert self.base_url is not None
        payload = {
            "api_key": self.api_key,
            "type": "text",
            "number": to_string,
            "senderid": self.sender_id or "",
            "message": message,
        }

        return payload

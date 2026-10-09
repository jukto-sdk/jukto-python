"""Adapter for AlphaSMS (sms.net.bd) SMS Gateway."""

from __future__ import annotations

from typing import Any, Optional
import httpx
from jukto._responses import decode_json, unexpected

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
from jukto.logger import logger


class AlphaSMSClient(BaseSMSProvider):
    """Adapter for AlphaSMS (sms.net.bd) API."""

    DEFAULT_URL = "https://api.sms.net.bd/sendsms"

    def __init__(
        self,
        api_key: str,
        sender_id: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float | httpx.Timeout = 30.0,
        *,
        allow_insecure_http: bool = False,
        http_client: Optional[httpx.Client] = None,
        limits: Optional[httpx.Limits] = None,
    ) -> None:
        super().__init__(
            api_key=api_key,
            sender_id=sender_id,
            base_url=base_url or self.DEFAULT_URL,
            timeout=timeout,
            allow_insecure_http=allow_insecure_http,
            http_client=http_client,
            limits=limits,
        )

    def _handle_http_status_error(self, exc: httpx.HTTPStatusError) -> None:
        status_code = exc.response.status_code
        text = exc.response.text.strip()
        error_message = f'AlphaSMS API error ({status_code}): [details withheld]'
        logger.error('provider=AlphaSMS operation=handle_http_status_error event=response status=%d', status_code)

        if status_code in (401, 403):
            raise ProviderAuthenticationError(
                error_message,
                status_code=status_code,
                response_body=text,
                provider="AlphaSMS",
            ) from None
        elif status_code == 429:
            raise ProviderRateLimitError(
                error_message,
                status_code=status_code,
                response_body=text,
                provider="AlphaSMS",
            ) from None
        elif status_code in (400, 422):
            raise InvalidRequestError(
                error_message,
                status_code=status_code,
                response_body=text,
                provider="AlphaSMS",
            ) from None
        elif status_code >= 500:
            raise ProviderServerError(
                error_message,
                status_code=status_code,
                response_body=text,
                provider="AlphaSMS",
            ) from None
        else:
            raise ProviderError(
                error_message,
                status_code=status_code,
                response_body=text,
                provider="AlphaSMS",
            ) from None

    def _inspect_response_data(self, data: Any, response: httpx.Response) -> dict[str, Any]:
        """Classify documented codes; provenance: tests/fixtures/alphasms_contract.json."""
        raw_code = data.get("error") if isinstance(data, dict) else None
        # The official JSON example uses integers; its C# examples use string codes.
        # Accept canonical decimal strings only, not bools, floats or coercible objects.
        if type(raw_code) is int:
            error_code = raw_code
        elif isinstance(raw_code, str) and len(raw_code) <= 10 and raw_code.isascii() and raw_code.isdecimal() and str(int(raw_code)) == raw_code:
            error_code = int(raw_code)
        else:
            raise unexpected(response, "AlphaSMS", data)

        if error_code == 0:
            submission = data.get("data")
            request_id = submission.get("request_id") if isinstance(submission, dict) else None
            if not ((type(request_id) is int and request_id >= 0) or (isinstance(request_id, str) and request_id)):
                raise unexpected(response, "AlphaSMS", data)
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
        error_message = f'AlphaSMS error ({error_code}): [details withheld]'
        logger.error('provider=AlphaSMS operation=inspect_response_data event=error')
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


        logger.debug('provider=AlphaSMS operation=send_sms event=request')

        try:
            response = self._transport.request("POST", self.base_url, data=payload)
            logger.debug('provider=AlphaSMS operation=send_sms event=response status=%d', response.status_code)
            response.raise_for_status()
            data = decode_json(response, "AlphaSMS")
            return self._inspect_response_data(data, response)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                'AlphaSMS request timed out: [details withheld]',
                provider="AlphaSMS",
            ) from None
        except httpx.HTTPStatusError as exc:
            self._handle_http_status_error(exc)
            raise
        except httpx.RequestError as exc:
            raise ProviderConnectionError(
                'Failed to connect to AlphaSMS: [details withheld]',
                provider="AlphaSMS",
            ) from None

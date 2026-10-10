"""Adapter for BulkSMSBD (bulksmsbd.net) SMS Gateway."""

from __future__ import annotations

from typing import Any, Optional
import httpx
from jukto._responses import decode_json

from jukto.exceptions import ProviderConnectionError, ProviderTimeoutError
from jukto.interfaces.sms import BaseSMSProvider
from jukto.logger import logger
from jukto._operations import operation


from ._bulksmsbd_contract import BulkSMSBDContract


class BulkSMSBDClient(BulkSMSBDContract, BaseSMSProvider):
    """Adapter for BulkSMSBD (bulksmsbd.net) API."""

    provider_name = "BulkSMSBD"

    DEFAULT_URL = "http://bulksmsbd.net/api/smsapi"

    def __init__(
        self,
        api_key: str,
        sender_id: str,
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


    @operation
    def send_sms(self, phone_numbers: str | list[str], message: str) -> dict[str, Any]:
        payload = self._prepare_sms(phone_numbers, message)
        assert self.base_url is not None

        logger.debug('provider=BulkSMSBD operation=send_sms event=request')

        try:
            response = self._transport.request("POST", self.base_url, data=payload)
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

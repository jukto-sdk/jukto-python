from __future__ import annotations

from typing import Any, Optional
import httpx

from jukto.exceptions import ProviderConnectionError, ProviderTimeoutError
from jukto.interfaces.asynchronous import AsyncBaseSMSProvider
from jukto.logger import logger
from jukto._operations import async_operation as operation


from ._greenweb_contract import GreenWebContract


class AsyncGreenWebClient(GreenWebContract, AsyncBaseSMSProvider):
    """Adapter for GreenWeb SMS API."""

    provider_name = "GreenWeb"

    DEFAULT_URL = "https://api.greenweb.com.bd/api.php"

    def __init__(
        self,
        api_key: str,
        sender_id: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float | httpx.Timeout = 30.0,
        *,
        allow_insecure_http: bool = False,
        http_client: Optional[httpx.AsyncClient] = None,
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
    async def send_sms(self, phone_numbers: str | list[str], message: str) -> dict[str, Any] | list[Any] | str:
        payload = self._prepare_sms(phone_numbers, message)
        assert self.base_url is not None

        logger.debug('provider=GreenWeb operation=send_sms event=request')

        try:
            response = await self._transport.request("POST", self.base_url, data=payload)
            logger.debug('provider=GreenWeb operation=send_sms event=response status=%d', response.status_code)
            response.raise_for_status()
            return self._inspect_response_content(response)
        except httpx.TimeoutException as exc:
            logger.error('provider=GreenWeb operation=send_sms event=timeout')
            raise ProviderTimeoutError(
                'Request to GreenWeb timed out: [details withheld]',
                provider="GreenWeb",
            ) from None
        except httpx.HTTPStatusError as exc:
            self._handle_http_status_error(exc)
        except httpx.RequestError as exc:
            logger.error('provider=GreenWeb operation=send_sms event=error')
            raise ProviderConnectionError(
                'Failed to connect to GreenWeb: [details withheld]',
                provider="GreenWeb",
            ) from None

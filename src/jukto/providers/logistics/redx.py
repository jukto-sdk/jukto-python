"""Adapter for RedX Logistics API."""

from __future__ import annotations

from typing import Any, Optional
import httpx
from jukto._transport import validate_endpoint

from jukto.exceptions import ProviderConnectionError, ProviderTimeoutError
from jukto.interfaces.logistics import BaseLogisticsProvider, Parcel
from jukto.logger import logger
from jukto._operations import operation


from ._redx_contract import RedXContract


class RedXClient(RedXContract, BaseLogisticsProvider):
    """Adapter for RedX Logistics API."""

    provider_name = "RedX"

    PRODUCTION_URL = "https://openapi.redx.com.bd/v1.0.0-beta"
    SANDBOX_URL = "https://sandbox.redx.com.bd/v1.0.0-beta"

    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = None,
        sandbox: bool = False,
        timeout: float | httpx.Timeout = 30.0,
        *,
        allow_insecure_http: bool = False,
        http_client: Optional[httpx.Client] = None,
        limits: Optional[httpx.Limits] = None,
    ) -> None:
        resolved_url = base_url or (self.SANDBOX_URL if sandbox else self.PRODUCTION_URL)
        super().__init__(
            api_key=api_key,
            secret_key=None,
            base_url=resolved_url,
            timeout=timeout,
            allow_insecure_http=allow_insecure_http,
            http_client=http_client,
            limits=limits,
        )
        self.headers = {
            "API-ACCESS-TOKEN": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }


    def _request(self, method: str, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        validate_endpoint(endpoint, self.allow_insecure_http)
        kwargs["follow_redirects"] = False

        logger.debug('provider=RedX operation=request event=request')

        try:
            response = self._transport.request(
                method=method,
                url=endpoint,
                headers=self.headers,
                **kwargs,
            )
            logger.debug('provider=RedX operation=request event=response status=%d', response.status_code)
            response.raise_for_status()
            return self._inspect_response(response, method, endpoint)
        except httpx.TimeoutException as exc:
            logger.error('provider=RedX operation=request event=timeout')
            raise ProviderTimeoutError(
                'Request to RedX timed out: [details withheld]',
                provider="RedX",
            ) from None
        except httpx.HTTPStatusError as exc:
            self._handle_http_status_error(exc)
            raise
        except httpx.RequestError as exc:
            logger.error('provider=RedX operation=request event=error')
            raise ProviderConnectionError(
                'Failed to connect to RedX: [details withheld]',
                provider="RedX",
            ) from None

    @operation
    def create_order(self, parcel: Parcel) -> dict[str, Any]:
        endpoint, payload = self._prepare_order(parcel)
        return self._request("POST", endpoint, json=payload)

    @operation
    def check_status(self, consignment_id: str) -> dict[str, Any]:
        endpoint = f"{self.base_url}/parcels/tracking/{consignment_id}"
        return self._request("GET", endpoint)

    @operation
    def _status_payload(self, consignment_id: str) -> dict[str, Any]:
        return self._request("GET", f"{self.base_url}/parcel/info/{consignment_id}")

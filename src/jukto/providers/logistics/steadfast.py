from __future__ import annotations

from typing import Any, Optional
import httpx
from jukto._transport import validate_endpoint

from jukto.exceptions import ProviderConnectionError, ProviderTimeoutError
from jukto.interfaces.logistics import BaseLogisticsProvider, Parcel
from jukto.logger import logger
from jukto._operations import operation


from ._steadfast_contract import SteadfastContract


class SteadfastClient(SteadfastContract, BaseLogisticsProvider):
    """Adapter for Steadfast Courier API."""

    provider_name = "Steadfast"

    DEFAULT_URL = "https://portal.packzy.com/api/v1"

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        base_url: Optional[str] = None,
        timeout: float | httpx.Timeout = 30.0,
        *,
        allow_insecure_http: bool = False,
        http_client: Optional[httpx.Client] = None,
        limits: Optional[httpx.Limits] = None,
    ) -> None:
        super().__init__(
            api_key=api_key,
            secret_key=secret_key,
            base_url=base_url or self.DEFAULT_URL,
            timeout=timeout,
            allow_insecure_http=allow_insecure_http,
            http_client=http_client,
            limits=limits,
        )
        self.headers = {
            "Api-Key": self.api_key,
            "Secret-Key": self.secret_key,
            "Content-Type": "application/json",
        }


    def _request(self, method: str, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        """Execute HTTP request with robust error handling and debug logging."""
        validate_endpoint(endpoint, self.allow_insecure_http)
        kwargs["follow_redirects"] = False

        logger.debug('provider=Steadfast operation=request event=request')

        try:
            response = self._transport.request(
                method=method,
                url=endpoint,
                headers=self.headers,
                **kwargs,
            )
            logger.debug('provider=Steadfast operation=request event=response status=%d', response.status_code)
            response.raise_for_status()
            return self._inspect_response(response, method, endpoint)
        except httpx.TimeoutException as exc:
            logger.error('provider=Steadfast operation=request event=error')
            raise ProviderTimeoutError(
                'Request to Steadfast timed out: [details withheld]',
                provider="Steadfast",
            ) from None
        except httpx.HTTPStatusError as exc:
            self._handle_http_status_error(exc)
        except httpx.RequestError as exc:
            logger.error('provider=Steadfast operation=request event=error')
            raise ProviderConnectionError(
                'Failed to connect to Steadfast: [details withheld]',
                provider="Steadfast",
            ) from None

    @operation
    def create_order(self, parcel: Parcel) -> dict[str, Any]:
        endpoint, payload = self._prepare_order(parcel)
        return self._request("POST", endpoint, json=payload)

    @operation
    def check_status(self, consignment_id: str) -> dict[str, Any]:
        endpoint = f"{self.base_url}/status_by_cid/{consignment_id}"
        return self._request("GET", endpoint)

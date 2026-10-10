"""Adapter for Pathao Courier API with OAuth2 token lifecycle management."""

from __future__ import annotations

import time
from asyncio import Lock
from typing import Any, Optional
import httpx
from jukto._responses import error_body
from jukto._transport import validate_endpoint

from jukto.exceptions import ProviderConnectionError, ProviderTimeoutError
from jukto.interfaces.asynchronous import AsyncBaseLogisticsProvider
from jukto.interfaces.logistics import Parcel
from jukto.logger import logger
from jukto._operations import async_operation as operation


from ._pathao_contract import PathaoContract


class AsyncPathaoClient(PathaoContract, AsyncBaseLogisticsProvider):
    """Adapter for Pathao Courier API.

    Implements automatic OAuth2 token issue, caching, and token refresh.
    """

    provider_name = "Pathao"

    PRODUCTION_URL = "https://api-hermes.pathao.com"
    SANDBOX_URL = "https://courier-api-sandbox.pathao.com"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        username: str,
        password: str,
        store_id: Optional[int] = None,
        base_url: Optional[str] = None,
        sandbox: bool = False,
        timeout: float | httpx.Timeout = 30.0,
        *,
        allow_insecure_http: bool = False,
        http_client: Optional[httpx.AsyncClient] = None,
        limits: Optional[httpx.Limits] = None,
        retry_unauthorized_orders: bool = False,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username
        self.password = password
        self.store_id = store_id
        self.sandbox = sandbox

        resolved_url = base_url or (self.SANDBOX_URL if sandbox else self.PRODUCTION_URL)
        super().__init__(
            api_key=client_id,
            secret_key=client_secret,
            base_url=resolved_url,
            timeout=timeout,
            allow_insecure_http=allow_insecure_http,
            http_client=http_client,
            limits=limits,
        )

        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.token_expiry: float = 0.0
        self.retry_unauthorized_orders = retry_unauthorized_orders
        self._token_lock = Lock()
        self._token_generation = 0
        self._refresh_margin = 60.0


    async def _exchange_token(self, refresh: bool) -> str:
        """Called under the token lock; publish only a fully validated response."""
        endpoint = f"{self.base_url}/aladdin/api/v1/issue-token"
        payload = self._token_payload(refresh)
        started = time.monotonic()
        logger.debug('provider=Pathao operation=exchange_token event=auth')
        try:
            response = await self._transport.request("POST", endpoint, json=payload,
                headers={"Accept": "application/json", "Content-Type": "application/json"})
            # RFC 6749 section 5.2: only this explicit rejection permits fallback.
            body = error_body(response) if response.status_code == 400 else None
            if refresh and isinstance(body, dict) and body.get("error") == "invalid_grant":
                return await self._exchange_token(False)
            response.raise_for_status()
            return self._publish_token(response, refresh, started)
        except httpx.TimeoutException:
            raise ProviderTimeoutError('Pathao token request timed out: [details withheld]', provider="Pathao") from None
        except httpx.HTTPStatusError as exc:
            self._handle_http_status_error(exc)
            raise
        except httpx.RequestError:
            raise ProviderConnectionError('Failed to connect to Pathao auth server: [details withheld]', provider="Pathao") from None

    async def _issue_token(self) -> str:
        async with self._token_lock:
            return await self._exchange_token(False)

    async def _refresh_access_token(self) -> str:
        async with self._token_lock:
            return await self._exchange_token(bool(self.refresh_token))

    async def _get_token_snapshot(self, rejected_generation: Optional[int] = None) -> tuple[str, int]:
        self._transport.ensure_open()
        # Recheck after acquiring the lock. A stale 401 cannot invalidate a newer token.
        async with self._token_lock:
            rejected = rejected_generation == self._token_generation
            if self.access_token and not rejected and time.monotonic() < self.token_expiry - self._refresh_margin:
                return self.access_token, self._token_generation
            token = await self._exchange_token(bool(self.refresh_token))
            return token, self._token_generation

    async def get_token(self) -> str:
        """Return a token from this instance's process-local, synchronized cache."""
        return (await self._get_token_snapshot())[0]


    async def _request(self, method: str, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        """Replay reads once on 401; shipment replay requires explicit opt-in."""
        validate_endpoint(endpoint, self.allow_insecure_http)
        kwargs["follow_redirects"] = False
        token, generation = await self._get_token_snapshot()
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        headers.update(kwargs.pop("headers", {}))
        replay = method.upper() == "GET" or (method.upper() == "POST" and endpoint.endswith("/orders") and self.retry_unauthorized_orders)
        for attempt in range(2):
            headers["Authorization"] = f"Bearer {token}"
            logger.debug('provider=Pathao operation=request event=request')
            try:
                response = await self._transport.request(method=method, url=endpoint, headers=headers, **kwargs)
                logger.debug('provider=Pathao operation=request event=response status=%d', response.status_code)
                response.raise_for_status()
                return self._inspect_response(response, endpoint)
            except httpx.TimeoutException:
                raise ProviderTimeoutError('Pathao request timed out: [details withheld]', provider="Pathao") from None
            except httpx.HTTPStatusError as exc:
                if attempt == 0 and replay and exc.response.status_code == 401:
                    token, generation = await self._get_token_snapshot(rejected_generation=generation)
                    continue
                self._handle_http_status_error(exc)
                raise
            except httpx.RequestError:
                raise ProviderConnectionError('Failed to connect to Pathao: [details withheld]', provider="Pathao") from None
        raise AssertionError("unreachable retry state")

    @operation
    async def create_order(self, parcel: Parcel) -> dict[str, Any]:
        endpoint, payload = self._prepare_order(parcel)
        return await self._request("POST", endpoint, json=payload)

    @operation
    async def check_status(self, consignment_id: str) -> dict[str, Any]:
        endpoint = f"{self.base_url}/aladdin/api/v1/orders/{consignment_id}/info"
        return await self._request("GET", endpoint)

    @operation
    async def get_stores(self) -> dict[str, Any]:
        """Fetch merchant store locations registered with Pathao."""
        endpoint = f"{self.base_url}/aladdin/api/v1/stores"
        return await self._request("GET", endpoint)

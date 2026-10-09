"""Adapter for Pathao Courier API with OAuth2 token lifecycle management."""

from __future__ import annotations

import time
import math
from threading import RLock
from typing import Any, Optional
import httpx
from jukto._responses import decode_json, error_body, require_object, unexpected
from jukto._transport import validate_endpoint

from jukto.exceptions import (
    InvalidRequestError,
    ProviderAuthenticationError,
    ProviderConnectionError,
    ProviderError,
    ProviderRateLimitError,
    ProviderServerError,
    ProviderTimeoutError,
    ResourceNotFoundError,
)
from jukto.interfaces.logistics import BaseLogisticsProvider, Parcel
from jukto.logger import logger
from jukto._shipments import validate_parcel, require_id, require_text


class PathaoClient(BaseLogisticsProvider):
    """Adapter for Pathao Courier API.

    Implements automatic OAuth2 token issue, caching, and token refresh.
    """

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
        http_client: Optional[httpx.Client] = None,
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
        self._token_lock = RLock()
        self._token_generation = 0
        self._refresh_margin = 60.0

    def _handle_http_status_error(self, exc: httpx.HTTPStatusError) -> None:
        status_code = exc.response.status_code
        body = error_body(exc.response)

        error_message = f'Pathao API error ({status_code}): [details withheld]'
        logger.error('provider=Pathao operation=handle_http_status_error event=error status=%d', status_code)

        if status_code in (401, 403):
            raise ProviderAuthenticationError(
                error_message,
                status_code=status_code,
                response_body=body,
                provider="Pathao",
            ) from None
        elif status_code == 404:
            raise ResourceNotFoundError(
                error_message,
                status_code=status_code,
                response_body=body,
                provider="Pathao",
            ) from None
        elif status_code in (400, 422):
            raise InvalidRequestError(
                error_message,
                status_code=status_code,
                response_body=body,
                provider="Pathao",
            ) from None
        elif status_code == 429:
            raise ProviderRateLimitError(
                error_message,
                status_code=status_code,
                response_body=body,
                provider="Pathao",
            ) from None
        elif status_code >= 500:
            raise ProviderServerError(
                error_message,
                status_code=status_code,
                response_body=body,
                provider="Pathao",
            ) from None
        else:
            raise ProviderError(
                error_message,
                status_code=status_code,
                response_body=body,
                provider="Pathao",
            ) from None

    def _exchange_token(self, refresh: bool) -> str:
        """Called under the token lock; publish only a fully validated response."""
        endpoint = f"{self.base_url}/aladdin/api/v1/issue-token"
        payload = {"client_id": self.client_id, "client_secret": self.client_secret}
        if refresh:
            payload.update(grant_type="refresh_token", refresh_token=self.refresh_token)
        else:
            payload.update(grant_type="password", username=self.username, password=self.password)
        started = time.monotonic()
        logger.debug('provider=Pathao operation=exchange_token event=auth')
        try:
            response = self._transport.request("POST", endpoint, json=payload,
                headers={"Accept": "application/json", "Content-Type": "application/json"})
            # RFC 6749 section 5.2: only this explicit rejection permits fallback.
            body = error_body(response) if response.status_code == 400 else None
            if refresh and isinstance(body, dict) and body.get("error") == "invalid_grant":
                return self._exchange_token(False)
            response.raise_for_status()
            data = require_object(decode_json(response, "Pathao"), response, "Pathao")
            access = data.get("access_token")
            rotation = data.get("refresh_token", self.refresh_token if refresh else None)
            expiry = data.get("expires_in")
            try:
                ttl = float(expiry)
            except (ValueError, TypeError, OverflowError):
                raise unexpected(response, "Pathao", data) from None
            if (not isinstance(access, str) or not access.strip()
                or (rotation is not None and (not isinstance(rotation, str) or not rotation.strip()))
                or ("refresh_token" in data and rotation is None)
                or isinstance(expiry, bool) or not math.isfinite(ttl) or ttl <= 0
                or not math.isfinite(started + ttl)):
                raise unexpected(response, "Pathao", data)
            self.access_token, self.refresh_token, self.token_expiry = access, rotation, started + ttl
            self._refresh_margin = min(60.0, ttl * 0.1)
            self._token_generation += 1
            return access
        except httpx.TimeoutException:
            raise ProviderTimeoutError('Pathao token request timed out: [details withheld]', provider="Pathao") from None
        except httpx.HTTPStatusError as exc:
            self._handle_http_status_error(exc)
            raise
        except httpx.RequestError:
            raise ProviderConnectionError('Failed to connect to Pathao auth server: [details withheld]', provider="Pathao") from None

    def _issue_token(self) -> str:
        with self._token_lock:
            return self._exchange_token(False)

    def _refresh_access_token(self) -> str:
        with self._token_lock:
            return self._exchange_token(bool(self.refresh_token))

    def _get_token_snapshot(self, rejected_generation: Optional[int] = None) -> tuple[str, int]:
        self._transport.ensure_open()
        # Recheck after acquiring the lock. A stale 401 cannot invalidate a newer token.
        with self._token_lock:
            rejected = rejected_generation == self._token_generation
            if self.access_token and not rejected and time.monotonic() < self.token_expiry - self._refresh_margin:
                return self.access_token, self._token_generation
            token = self._exchange_token(bool(self.refresh_token))
            return token, self._token_generation

    def get_token(self) -> str:
        """Return a token from this instance's process-local, synchronized cache."""
        return self._get_token_snapshot()[0]

    def _inspect_response(self, response: httpx.Response, endpoint: str) -> dict[str, Any]:
        """Conservative legacy envelope guard; official application codes unresolved."""
        data = require_object(decode_json(response, "Pathao"), response, "Pathao")
        # Do not guess the semantics of error/type/status codes from HTTP conventions.
        if data.get("type") not in (None, "success") or data.get("error") or data.get("errors"):
            raise unexpected(response, "Pathao", data)
        content = data.get("data")
        if not ((isinstance(content, dict) and bool(content)) or isinstance(content, list)):
            raise unexpected(response, "Pathao", data)
        if endpoint.endswith("/orders"):
            valid = isinstance(content, dict) and bool(content.get("consignment_id"))
        elif endpoint.endswith("/info"):
            valid = isinstance(content, dict) and isinstance(content.get("order_status"), str) and bool(content["order_status"])
        else:
            valid = isinstance(content, (dict, list))
        if not valid:
            raise unexpected(response, "Pathao", data)
        return data

    def _request(self, method: str, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        """Replay reads once on 401; shipment replay requires explicit opt-in."""
        validate_endpoint(endpoint, self.allow_insecure_http)
        kwargs["follow_redirects"] = False
        token, generation = self._get_token_snapshot()
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        headers.update(kwargs.pop("headers", {}))
        replay = method.upper() == "GET" or (method.upper() == "POST" and endpoint.endswith("/orders") and self.retry_unauthorized_orders)
        for attempt in range(2):
            headers["Authorization"] = f"Bearer {token}"
            logger.debug('provider=Pathao operation=request event=request')
            try:
                response = self._transport.request(method=method, url=endpoint, headers=headers, **kwargs)
                logger.debug('provider=Pathao operation=request event=response status=%d', response.status_code)
                response.raise_for_status()
                return self._inspect_response(response, endpoint)
            except httpx.TimeoutException:
                raise ProviderTimeoutError('Pathao request timed out: [details withheld]', provider="Pathao") from None
            except httpx.HTTPStatusError as exc:
                if attempt == 0 and replay and exc.response.status_code == 401:
                    token, generation = self._get_token_snapshot(rejected_generation=generation)
                    continue
                self._handle_http_status_error(exc)
                raise
            except httpx.RequestError:
                raise ProviderConnectionError('Failed to connect to Pathao: [details withheld]', provider="Pathao") from None
        raise AssertionError("unreachable retry state")

    def create_order(self, parcel: Parcel) -> dict[str, Any]:
        validate_parcel(parcel, "Pathao")
        for name in ("client_id", "client_secret", "username", "password"):
            require_text(getattr(self, name), name, "Pathao")
        store_id = self.store_id if parcel.store_id is None else parcel.store_id
        require_id(store_id, "store_id", "Pathao")
        for name in ("recipient_city", "recipient_zone", "recipient_area"):
            value = getattr(parcel, name)
            if value is not None:
                require_id(value, name, "Pathao")
        require_id(parcel.item_type, "item_type", "Pathao")
        require_id(parcel.delivery_type, "delivery_type", "Pathao")

        endpoint = f"{self.base_url}/aladdin/api/v1/orders"
        payload = {
            "store_id": store_id,
            "merchant_order_id": parcel.invoice_id,
            "recipient_name": parcel.recipient_name,
            "recipient_phone": parcel.recipient_phone,
            "recipient_address": parcel.recipient_address,
            "delivery_type": parcel.delivery_type,
            "item_type": parcel.item_type,
            "special_instruction": parcel.note or "",
            "item_quantity": parcel.item_quantity,
            "item_weight": parcel.item_weight,
            "amount_to_collect": parcel.cod_amount,
        }
        for name in ("recipient_city", "recipient_zone", "recipient_area"):
            if getattr(parcel, name) is not None:
                payload[name] = getattr(parcel, name)
        return self._request("POST", endpoint, json=payload)

    def check_status(self, consignment_id: str) -> dict[str, Any]:
        endpoint = f"{self.base_url}/aladdin/api/v1/orders/{consignment_id}/info"
        return self._request("GET", endpoint)

    def get_stores(self) -> dict[str, Any]:
        """Fetch merchant store locations registered with Pathao."""
        endpoint = f"{self.base_url}/aladdin/api/v1/stores"
        return self._request("GET", endpoint)

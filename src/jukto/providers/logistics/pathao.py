"""Adapter for Pathao Courier API with OAuth2 token lifecycle management."""

from __future__ import annotations

import time
import math
from typing import Any, Optional
import httpx
from jukto._responses import decode_json, error_body, require_object, unexpected
from jukto._transport import secure_http_client, validate_endpoint

from jukto.exceptions import (
    InvalidRequestError,
    JuktoValidationError,
    ProviderAuthenticationError,
    ProviderConnectionError,
    ProviderError,
    ProviderRateLimitError,
    ProviderServerError,
    ProviderTimeoutError,
    ResourceNotFoundError,
    UnexpectedProviderResponseError,
)
from jukto.interfaces.logistics import BaseLogisticsProvider, Parcel
from jukto.logger import logger


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
        timeout: float = 30.0,
        *,
        allow_insecure_http: bool = False,
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
        )

        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.token_expiry: float = 0.0

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

    def _issue_token(self) -> str:
        """Authenticate with Pathao and obtain OAuth2 tokens."""
        endpoint = f"{self.base_url}/aladdin/api/v1/issue-token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "username": self.username,
            "password": self.password,
            "grant_type": "password",
        }
        logger.debug('provider=Pathao operation=issue_token event=auth')

        try:
            with secure_http_client(endpoint, self.timeout, self.allow_insecure_http) as client:
                response = client.post(
                    endpoint,
                    json=payload,
                    headers={"Accept": "application/json", "Content-Type": "application/json"},
                )
                response.raise_for_status()
                data = require_object(decode_json(response, "Pathao"), response, "Pathao")
                if not isinstance(data.get("access_token"), str) or not data["access_token"]:
                    raise unexpected(response, "Pathao", data)
                self.access_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")
                expires_in = data.get("expires_in", 3600)
                try:
                    ttl = float(expires_in)
                except (ValueError, TypeError, OverflowError):
                    raise unexpected(response, "Pathao", data) from None
                if isinstance(expires_in, bool) or not math.isfinite(ttl) or ttl <= 0:
                    raise unexpected(response, "Pathao", data)
                self.token_expiry = time.time() + ttl
                logger.debug('provider=Pathao operation=issue_token event=auth')
                return self.access_token
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                'Pathao token request timed out: [details withheld]',
                provider="Pathao",
            ) from None
        except httpx.HTTPStatusError as exc:
            self._handle_http_status_error(exc)
            raise
        except httpx.RequestError as exc:
            raise ProviderConnectionError(
                'Failed to connect to Pathao auth server: [details withheld]',
                provider="Pathao",
            ) from None

    def _refresh_access_token(self) -> str:
        """Refresh an expired OAuth2 access token."""
        if not self.refresh_token:
            return self._issue_token()

        endpoint = f"{self.base_url}/aladdin/api/v1/issue-token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
        }
        logger.debug('provider=Pathao operation=refresh_access_token event=auth')

        try:
            with secure_http_client(endpoint, self.timeout, self.allow_insecure_http) as client:
                response = client.post(
                    endpoint,
                    json=payload,
                    headers={"Accept": "application/json", "Content-Type": "application/json"},
                )
                response.raise_for_status()
                data = require_object(decode_json(response, "Pathao"), response, "Pathao")
                if not isinstance(data.get("access_token"), str) or not data["access_token"]:
                    raise unexpected(response, "Pathao", data)
                self.access_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token", self.refresh_token)
                expires_in = data.get("expires_in", 3600)
                try:
                    ttl = float(expires_in)
                except (ValueError, TypeError, OverflowError):
                    raise unexpected(response, "Pathao", data) from None
                if isinstance(expires_in, bool) or not math.isfinite(ttl) or ttl <= 0:
                    raise unexpected(response, "Pathao", data)
                self.token_expiry = time.time() + ttl
                logger.debug('provider=Pathao operation=refresh_access_token event=auth')
                return self.access_token
        except UnexpectedProviderResponseError:
            raise
        except (httpx.RequestError, httpx.HTTPStatusError, ProviderError):
            logger.warning('provider=Pathao operation=refresh_access_token event=error')
            return self._issue_token()

    def get_token(self) -> str:
        """Returns a valid access token, issuing or refreshing as necessary."""
        # Refresh 60 seconds before actual expiration
        if self.access_token and time.time() < (self.token_expiry - 60):
            return self.access_token

        if self.refresh_token:
            return self._refresh_access_token()

        return self._issue_token()

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
        """Execute an authenticated HTTP request to Pathao API."""
        validate_endpoint(endpoint, self.allow_insecure_http)
        kwargs["follow_redirects"] = False
        token = self.get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))


        logger.debug('provider=Pathao operation=request event=request')

        try:
            with secure_http_client(endpoint, self.timeout, self.allow_insecure_http) as client:
                response = client.request(
                    method=method,
                    url=endpoint,
                    headers=headers,
                    **kwargs,
                )
                logger.debug('provider=Pathao operation=request event=response status=%d', response.status_code)
                response.raise_for_status()
                return self._inspect_response(response, endpoint)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                'Pathao request timed out: [details withheld]',
                provider="Pathao",
            ) from None
        except httpx.HTTPStatusError as exc:
            # If token expired unexpectedly, try refreshing once
            if exc.response.status_code == 401 and self.refresh_token:
                logger.info('provider=Pathao operation=request event=auth')
                self.token_expiry = 0.0
                token = self._refresh_access_token()
                headers["Authorization"] = f"Bearer {token}"
                try:
                    with secure_http_client(endpoint, self.timeout, self.allow_insecure_http) as client:
                        retry_resp = client.request(
                            method=method,
                            url=endpoint,
                            headers=headers,
                            **kwargs,
                        )
                        retry_resp.raise_for_status()
                        return self._inspect_response(retry_resp, endpoint)
                except (httpx.RequestError, httpx.HTTPStatusError):
                    pass
            self._handle_http_status_error(exc)
            raise
        except httpx.RequestError as exc:
            raise ProviderConnectionError(
                'Failed to connect to Pathao: [details withheld]',
                provider="Pathao",
            ) from None

    def create_order(self, parcel: Parcel) -> dict[str, Any]:
        store_id = parcel.store_id or self.store_id
        if not store_id:
            raise JuktoValidationError(
                "store_id is required for Pathao orders. Pass store_id in PathaoClient(...) or Parcel(store_id=...).",
                provider="Pathao",
            )

        endpoint = f"{self.base_url}/aladdin/api/v1/orders"
        payload = {
            "store_id": store_id,
            "merchant_order_id": parcel.invoice_id,
            "recipient_name": parcel.recipient_name,
            "recipient_phone": parcel.recipient_phone,
            "recipient_address": parcel.recipient_address,
            "recipient_city": parcel.recipient_city or 1,
            "recipient_zone": parcel.recipient_zone or 1,
            "recipient_area": parcel.recipient_area or 1,
            "delivery_type": parcel.delivery_type,
            "item_type": parcel.item_type,
            "special_instruction": parcel.note or "",
            "item_quantity": parcel.item_quantity,
            "item_weight": parcel.item_weight,
            "amount_to_collect": parcel.cod_amount,
        }
        return self._request("POST", endpoint, json=payload)

    def check_status(self, consignment_id: str) -> dict[str, Any]:
        endpoint = f"{self.base_url}/aladdin/api/v1/orders/{consignment_id}/info"
        return self._request("GET", endpoint)

    def get_stores(self) -> dict[str, Any]:
        """Fetch merchant store locations registered with Pathao."""
        endpoint = f"{self.base_url}/aladdin/api/v1/stores"
        return self._request("GET", endpoint)

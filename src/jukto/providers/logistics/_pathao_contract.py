"""Adapter for Pathao Courier API with OAuth2 token lifecycle management."""

from __future__ import annotations

import math
from typing import Any, NoReturn
import httpx
from jukto._responses import decode_json, error_body, require_object, unexpected

from jukto.exceptions import InvalidRequestError, ProviderAuthenticationError, ProviderError, ProviderRateLimitError, ProviderServerError, ResourceNotFoundError
from jukto.interfaces.logistics import Parcel
from jukto.logger import logger
from jukto._shipments import wire_amount, resolve_options, validate_parcel, require_id, require_text


class PathaoContract:
    client_id: str
    client_secret: str
    username: str
    password: str
    _refresh_margin: float
    _token_generation: int
    access_token: str | None
    base_url: str | None
    provider_name: str
    refresh_token: str | None
    store_id: int | None
    token_expiry: float

    def _handle_http_status_error(self, exc: httpx.HTTPStatusError) -> NoReturn:
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


    def _prepare_order(self, parcel: Parcel) -> tuple[str, dict[str, Any]]:
        parcel = resolve_options(parcel, self.provider_name)
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
            "amount_to_collect": wire_amount(parcel.cod_amount, "Pathao"),
        }
        for name in ("recipient_city", "recipient_zone", "recipient_area"):
            if getattr(parcel, name) is not None:
                payload[name] = getattr(parcel, name)
        return endpoint, payload


    def _publish_token(self, response: httpx.Response, refresh: bool, started: float) -> str:
        data = require_object(decode_json(response, "Pathao"), response, "Pathao")
        access = data.get("access_token")
        rotation = data.get("refresh_token", self.refresh_token if refresh else None)
        expiry: Any = data.get("expires_in")
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

    def _token_payload(self, refresh: bool) -> dict[str, Any]:
        payload: dict[str, Any] = {"client_id": self.client_id, "client_secret": self.client_secret}
        if refresh:
            payload.update(grant_type="refresh_token", refresh_token=self.refresh_token)
        else:
            payload.update(grant_type="password", username=self.username, password=self.password)
        return payload

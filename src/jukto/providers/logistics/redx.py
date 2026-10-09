"""Adapter for RedX Logistics API."""

from __future__ import annotations

from typing import Any, Optional
from decimal import Decimal
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
from jukto._shipments import validate_parcel, require_text, require_id, require_number
from jukto.exceptions import JuktoValidationError


class RedXClient(BaseLogisticsProvider):
    """Adapter for RedX Logistics API."""

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

    def _handle_http_status_error(self, exc: httpx.HTTPStatusError) -> None:
        status_code = exc.response.status_code
        body = error_body(exc.response)

        error_message = f'RedX API error ({status_code}): [details withheld]'
        logger.error('provider=RedX operation=handle_http_status_error event=error status=%d', status_code)

        if status_code in (401, 403):
            raise ProviderAuthenticationError(
                error_message,
                status_code=status_code,
                response_body=body,
                provider="RedX",
            ) from None
        elif status_code == 404:
            raise ResourceNotFoundError(
                error_message,
                status_code=status_code,
                response_body=body,
                provider="RedX",
            ) from None
        elif status_code in (400, 422):
            raise InvalidRequestError(
                error_message,
                status_code=status_code,
                response_body=body,
                provider="RedX",
            ) from None
        elif status_code == 429:
            raise ProviderRateLimitError(
                error_message,
                status_code=status_code,
                response_body=body,
                provider="RedX",
            ) from None
        elif status_code >= 500:
            raise ProviderServerError(
                error_message,
                status_code=status_code,
                response_body=body,
                provider="RedX",
            ) from None
        else:
            raise ProviderError(
                error_message,
                status_code=status_code,
                response_body=body,
                provider="RedX",
            ) from None

    def _handle_inline_errors(self, data: Any) -> None:
        if not isinstance(data, dict):
            return

        status = data.get("status")
        # RedX returns {"status": "error", "message": "..."} in some endpoints
        if status == "error" or (isinstance(status, int) and status >= 400):
            message = data.get("message") or data.get("error") or "RedX returned an error"
            code = status if isinstance(status, int) else 400
            error_message = 'RedX error: [details withheld]'
            logger.error('provider=RedX operation=handle_inline_errors event=error')

            if code in (401, 403) or "unauthorized" in str(message).lower():
                raise ProviderAuthenticationError(
                    error_message,
                    status_code=code,
                    response_body=data,
                    provider="RedX",
                )
            elif code == 404:
                raise ResourceNotFoundError(
                    error_message,
                    status_code=code,
                    response_body=data,
                    provider="RedX",
                )
            elif code in (400, 422):
                raise InvalidRequestError(
                    error_message,
                    status_code=code,
                    response_body=data,
                    provider="RedX",
                )
            else:
                raise ProviderError(
                    error_message,
                    status_code=code,
                    response_body=data,
                    provider="RedX",
                )

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
            data = require_object(decode_json(response, "RedX"), response, "RedX")
            self._handle_inline_errors(data)
            content = data.get("tracking_id") if method == "POST" else data.get("tracking")
            if method == "POST":
                valid = isinstance(content, (str, int)) and not isinstance(content, bool) and bool(content)
            else:
                valid = isinstance(content, dict) and isinstance(content.get("status"), str) and bool(content["status"])
            if not valid:
                raise unexpected(response, "RedX", data)
            return data
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

    def create_order(self, parcel: Parcel) -> dict[str, Any]:
        validate_parcel(parcel, "RedX")
        require_text(self.api_key, "api_key", "RedX")
        require_text(parcel.redx_delivery_area, "redx_delivery_area", "RedX")
        require_id(parcel.redx_delivery_area_id, "redx_delivery_area_id", "RedX")
        require_number(parcel.declared_value, "declared_value", "RedX")
        if parcel.redx_pickup_store_id is not None:
            require_id(parcel.redx_pickup_store_id, "redx_pickup_store_id", "RedX")
        grams = Decimal(str(parcel.item_weight)) * 1000
        if grams != grams.to_integral_value():
            raise JuktoValidationError('item_weight must represent a whole number of grams.', provider="RedX")
        endpoint = f"{self.base_url}/parcel"
        payload = {
            "customer_name": parcel.recipient_name,
            "customer_phone": parcel.recipient_phone,
            "delivery_area": parcel.redx_delivery_area,
            "delivery_area_id": parcel.redx_delivery_area_id,
            "customer_address": parcel.recipient_address,
            "merchant_invoice_id": parcel.invoice_id,
            "cash_collection_amount": parcel.cod_amount,
            "parcel_weight": int(grams),
            "instruction": parcel.note or "",
            "value": parcel.declared_value,
        }
        if parcel.redx_pickup_store_id is not None:
            payload["pickup_store_id"] = parcel.redx_pickup_store_id
        return self._request("POST", endpoint, json=payload)

    def check_status(self, consignment_id: str) -> dict[str, Any]:
        endpoint = f"{self.base_url}/parcels/tracking/{consignment_id}"
        return self._request("GET", endpoint)

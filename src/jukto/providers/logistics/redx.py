"""Adapter for RedX Logistics API."""

from __future__ import annotations

from typing import Any, Optional
import httpx
from jukto._transport import secure_http_client, validate_endpoint

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
from jukto.logger import logger, mask_sensitive


class RedXClient(BaseLogisticsProvider):
    """Adapter for RedX Logistics API."""

    PRODUCTION_URL = "https://openapi.redx.com.bd/v1.0.0-beta"
    SANDBOX_URL = "https://sandbox.redx.com.bd/v1.0.0-beta"

    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = None,
        sandbox: bool = False,
        timeout: float = 30.0,
        *,
        allow_insecure_http: bool = False,
    ) -> None:
        resolved_url = base_url or (self.SANDBOX_URL if sandbox else self.PRODUCTION_URL)
        super().__init__(
            api_key=api_key,
            secret_key=None,
            base_url=resolved_url,
            timeout=timeout,
            allow_insecure_http=allow_insecure_http,
        )
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _handle_http_status_error(self, exc: httpx.HTTPStatusError) -> None:
        status_code = exc.response.status_code
        try:
            body = exc.response.json()
            message = (
                body.get("message")
                or body.get("error")
                or (str(body.get("errors")) if body.get("errors") else None)
                or str(body)
            )
        except Exception:
            body = exc.response.text
            message = body.strip() or exc.response.reason_phrase

        error_message = f"RedX API error ({status_code}): {message}"
        logger.error("RedX HTTP error [%d]: %s", status_code, message)

        if status_code in (401, 403):
            raise ProviderAuthenticationError(
                error_message,
                status_code=status_code,
                response_body=body,
                provider="RedX",
            ) from exc
        elif status_code == 404:
            raise ResourceNotFoundError(
                error_message,
                status_code=status_code,
                response_body=body,
                provider="RedX",
            ) from exc
        elif status_code in (400, 422):
            raise InvalidRequestError(
                error_message,
                status_code=status_code,
                response_body=body,
                provider="RedX",
            ) from exc
        elif status_code == 429:
            raise ProviderRateLimitError(
                error_message,
                status_code=status_code,
                response_body=body,
                provider="RedX",
            ) from exc
        elif status_code >= 500:
            raise ProviderServerError(
                error_message,
                status_code=status_code,
                response_body=body,
                provider="RedX",
            ) from exc
        else:
            raise ProviderError(
                error_message,
                status_code=status_code,
                response_body=body,
                provider="RedX",
            ) from exc

    def _handle_inline_errors(self, data: Any) -> None:
        if not isinstance(data, dict):
            return

        status = data.get("status")
        # RedX returns {"status": "error", "message": "..."} in some endpoints
        if status == "error" or (isinstance(status, int) and status >= 400):
            message = data.get("message") or data.get("error") or "RedX returned an error"
            code = status if isinstance(status, int) else 400
            error_message = f"RedX error: {message}"
            logger.error("RedX inline error: %s", error_message)

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
        masked_json = mask_sensitive(kwargs.get("json")) if "json" in kwargs else None
        logger.debug("RedX request: %s %s | payload: %s", method, endpoint, masked_json)

        try:
            with secure_http_client(endpoint, self.timeout, self.allow_insecure_http) as client:
                response = client.request(
                    method=method,
                    url=endpoint,
                    headers=self.headers,
                    **kwargs,
                )
                logger.debug("RedX response [%d]: %s", response.status_code, response.text[:200])
                response.raise_for_status()
                data = response.json()
                self._handle_inline_errors(data)
                return data
        except httpx.TimeoutException as exc:
            logger.error("RedX request timeout: %s", exc)
            raise ProviderTimeoutError(
                f"Request to RedX timed out: {exc}",
                provider="RedX",
            ) from exc
        except httpx.HTTPStatusError as exc:
            self._handle_http_status_error(exc)
            raise
        except httpx.RequestError as exc:
            logger.error("RedX network failure: %s", exc)
            raise ProviderConnectionError(
                f"Failed to connect to RedX: {exc}",
                provider="RedX",
            ) from exc

    def create_order(self, parcel: Parcel) -> dict[str, Any]:
        endpoint = f"{self.base_url}/parcels"
        payload = {
            "customer_name": parcel.recipient_name,
            "customer_phone": parcel.recipient_phone,
            "delivery_area": parcel.recipient_address,
            "customer_address": parcel.recipient_address,
            "merchant_invoice_id": parcel.invoice_id,
            "cash_collection_amount": parcel.cod_amount,
            "parcel_weight": int(parcel.item_weight * 1000) if parcel.item_weight else 500,
            "instruction": parcel.note or "",
            "value": parcel.cod_amount,
        }
        return self._request("POST", endpoint, json=payload)

    def check_status(self, consignment_id: str) -> dict[str, Any]:
        endpoint = f"{self.base_url}/parcels/tracking/{consignment_id}"
        return self._request("GET", endpoint)

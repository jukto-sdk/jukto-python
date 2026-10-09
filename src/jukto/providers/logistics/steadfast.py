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


class SteadfastClient(BaseLogisticsProvider):
    """Adapter for Steadfast Courier API."""

    DEFAULT_URL = "https://portal.packzy.com/api/v1"

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
        *,
        allow_insecure_http: bool = False,
    ) -> None:
        super().__init__(
            api_key=api_key,
            secret_key=secret_key,
            base_url=base_url or self.DEFAULT_URL,
            timeout=timeout,
            allow_insecure_http=allow_insecure_http,
        )
        self.headers = {
            "Api-Key": self.api_key,
            "Secret-Key": self.secret_key,
            "Content-Type": "application/json",
        }

    def _handle_http_status_error(self, exc: httpx.HTTPStatusError) -> None:
        """Map httpx.HTTPStatusError to normalized Jukto exceptions."""
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

        error_message = f"Steadfast API error ({status_code}): {message}"
        logger.error("Steadfast HTTP error [%d]: %s", status_code, message)

        if status_code in (401, 403):
            raise ProviderAuthenticationError(
                error_message,
                status_code=status_code,
                response_body=body,
                provider="Steadfast",
            ) from exc
        elif status_code == 404:
            raise ResourceNotFoundError(
                error_message,
                status_code=status_code,
                response_body=body,
                provider="Steadfast",
            ) from exc
        elif status_code in (400, 422):
            raise InvalidRequestError(
                error_message,
                status_code=status_code,
                response_body=body,
                provider="Steadfast",
            ) from exc
        elif status_code == 429:
            raise ProviderRateLimitError(
                error_message,
                status_code=status_code,
                response_body=body,
                provider="Steadfast",
            ) from exc
        elif status_code >= 500:
            raise ProviderServerError(
                error_message,
                status_code=status_code,
                response_body=body,
                provider="Steadfast",
            ) from exc
        else:
            raise ProviderError(
                error_message,
                status_code=status_code,
                response_body=body,
                provider="Steadfast",
            ) from exc

    def _handle_inline_errors(self, data: Any) -> None:
        """Handle cases where Steadfast returns HTTP 200 with an error payload."""
        if not isinstance(data, dict):
            return

        status = data.get("status")
        if isinstance(status, int) and status >= 400:
            message = (
                data.get("message")
                or data.get("error")
                or (str(data.get("errors")) if data.get("errors") else "Unknown error")
            )
            error_message = f"Steadfast error ({status}): {message}"
            logger.error("Steadfast inline error [%d]: %s", status, message)

            if status in (401, 403):
                raise ProviderAuthenticationError(
                    error_message,
                    status_code=status,
                    response_body=data,
                    provider="Steadfast",
                )
            elif status == 404:
                raise ResourceNotFoundError(
                    error_message,
                    status_code=status,
                    response_body=data,
                    provider="Steadfast",
                )
            elif status in (400, 422):
                raise InvalidRequestError(
                    error_message,
                    status_code=status,
                    response_body=data,
                    provider="Steadfast",
                )
            else:
                raise ProviderError(
                    error_message,
                    status_code=status,
                    response_body=data,
                    provider="Steadfast",
                )

    def _request(self, method: str, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        """Execute HTTP request with robust error handling and debug logging."""
        validate_endpoint(endpoint, self.allow_insecure_http)
        kwargs["follow_redirects"] = False
        masked_json = mask_sensitive(kwargs.get("json")) if "json" in kwargs else None
        logger.debug(
            "Steadfast request: %s %s | payload: %s",
            method,
            endpoint,
            masked_json,
        )

        try:
            with secure_http_client(endpoint, self.timeout, self.allow_insecure_http) as client:
                response = client.request(
                    method=method,
                    url=endpoint,
                    headers=self.headers,
                    **kwargs,
                )
                logger.debug(
                    "Steadfast response [%d]: %s",
                    response.status_code,
                    response.text[:200] if len(response.text) > 200 else response.text,
                )
                response.raise_for_status()
                data = response.json()
                self._handle_inline_errors(data)
                return data
        except httpx.TimeoutException as exc:
            logger.error("Steadfast timeout on %s %s: %s", method, endpoint, exc)
            raise ProviderTimeoutError(
                f"Request to Steadfast timed out: {exc}",
                provider="Steadfast",
            ) from exc
        except httpx.HTTPStatusError as exc:
            self._handle_http_status_error(exc)
        except httpx.RequestError as exc:
            logger.error("Steadfast network error on %s %s: %s", method, endpoint, exc)
            raise ProviderConnectionError(
                f"Failed to connect to Steadfast: {exc}",
                provider="Steadfast",
            ) from exc

    def create_order(self, parcel: Parcel) -> dict[str, Any]:
        endpoint = f"{self.base_url}/create_order"
        payload = {
            "invoice": parcel.invoice_id,
            "recipient_name": parcel.recipient_name,
            "recipient_phone": parcel.recipient_phone,
            "recipient_address": parcel.recipient_address,
            "cod_amount": parcel.cod_amount,
            "note": parcel.note or "",
        }
        return self._request("POST", endpoint, json=payload)

    def check_status(self, consignment_id: str) -> dict[str, Any]:
        endpoint = f"{self.base_url}/status_by_cid/{consignment_id}"
        return self._request("GET", endpoint)

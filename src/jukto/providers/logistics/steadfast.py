from __future__ import annotations

from typing import Any, Optional
import httpx
from jukto._responses import decode_json, error_body, require_object, unexpected
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
from jukto.logger import logger


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
        body = error_body(exc.response)

        error_message = f'Steadfast API error ({status_code}): [details withheld]'
        logger.error('provider=Steadfast operation=handle_http_status_error event=error status=%d', status_code)

        if status_code in (401, 403):
            raise ProviderAuthenticationError(
                error_message,
                status_code=status_code,
                response_body=body,
                provider="Steadfast",
            ) from None
        elif status_code == 404:
            raise ResourceNotFoundError(
                error_message,
                status_code=status_code,
                response_body=body,
                provider="Steadfast",
            ) from None
        elif status_code in (400, 422):
            raise InvalidRequestError(
                error_message,
                status_code=status_code,
                response_body=body,
                provider="Steadfast",
            ) from None
        elif status_code == 429:
            raise ProviderRateLimitError(
                error_message,
                status_code=status_code,
                response_body=body,
                provider="Steadfast",
            ) from None
        elif status_code >= 500:
            raise ProviderServerError(
                error_message,
                status_code=status_code,
                response_body=body,
                provider="Steadfast",
            ) from None
        else:
            raise ProviderError(
                error_message,
                status_code=status_code,
                response_body=body,
                provider="Steadfast",
            ) from None

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
            error_message = f'Steadfast error ({status}): [details withheld]'
            logger.error('provider=Steadfast operation=handle_inline_errors event=error')

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

        logger.debug('provider=Steadfast operation=request event=request')

        try:
            with secure_http_client(endpoint, self.timeout, self.allow_insecure_http) as client:
                response = client.request(
                    method=method,
                    url=endpoint,
                    headers=self.headers,
                    **kwargs,
                )
                logger.debug('provider=Steadfast operation=request event=response status=%d', response.status_code)
                response.raise_for_status()
                data = require_object(decode_json(response, "Steadfast"), response, "Steadfast")
                self._handle_inline_errors(data)
                content = data.get("consignment") if method == "POST" else data.get("delivery_status")
                content_type = dict if method == "POST" else str
                valid = (
                    type(data.get("status")) is int and data["status"] == 200
                    and isinstance(content, content_type) and bool(content)
                    and (method != "POST" or bool(content.get("consignment_id")))
                )
                if not valid:
                    raise unexpected(response, "Steadfast", data)
                return data
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

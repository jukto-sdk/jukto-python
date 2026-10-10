from __future__ import annotations

from typing import Any, NoReturn
import httpx
from jukto._responses import decode_json, error_body, require_object, unexpected

from jukto.exceptions import InvalidRequestError, ProviderAuthenticationError, ProviderError, ProviderRateLimitError, ProviderServerError, ResourceNotFoundError
from jukto.interfaces.logistics import Parcel
from jukto.logger import logger
from jukto._shipments import wire_amount, resolve_options, validate_parcel, require_text


class SteadfastContract:
    api_key: str
    base_url: str | None
    provider_name: str
    secret_key: str | None

    def _handle_http_status_error(self, exc: httpx.HTTPStatusError) -> NoReturn:
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


    def _prepare_order(self, parcel: Parcel) -> tuple[str, dict[str, Any]]:
        parcel = resolve_options(parcel, self.provider_name)
        validate_parcel(parcel, "Steadfast")
        require_text(self.api_key, "api_key", "Steadfast")
        require_text(self.secret_key, "secret_key", "Steadfast")
        endpoint = f"{self.base_url}/create_order"
        payload = {
            "invoice": parcel.invoice_id,
            "recipient_name": parcel.recipient_name,
            "recipient_phone": parcel.recipient_phone,
            "recipient_address": parcel.recipient_address,
            "cod_amount": wire_amount(parcel.cod_amount, "Steadfast"),
            "note": parcel.note or "",
        }
        return endpoint, payload


    def _inspect_response(self, response: httpx.Response, method: str, endpoint: str) -> dict[str, Any]:
        data = require_object(decode_json(response, "Steadfast"), response, "Steadfast")
        self._handle_inline_errors(data)
        content = data.get("consignment") if method == "POST" else data.get("delivery_status")
        content_type = dict if method == "POST" else str
        valid = (
            type(data.get("status")) is int and data["status"] == 200
            and isinstance(content, content_type) and bool(content)
            and (method != "POST" or (isinstance(content, dict) and bool(content.get("consignment_id"))))
        )
        if not valid:
            raise unexpected(response, "Steadfast", data)
        return data

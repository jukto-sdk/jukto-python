from __future__ import annotations

from typing import Any, Optional
import httpx
from jukto._transport import secure_http_client

from jukto.exceptions import (
    InsufficientBalanceError,
    InvalidRequestError,
    ProviderAuthenticationError,
    ProviderConnectionError,
    ProviderError,
    ProviderRateLimitError,
    ProviderServerError,
    ProviderTimeoutError,
)
from jukto.interfaces.sms import BaseSMSProvider
from jukto.logger import logger, mask_sensitive


class GreenWebClient(BaseSMSProvider):
    """Adapter for GreenWeb SMS API."""

    DEFAULT_URL = "https://api.greenweb.com.bd/api.php"

    def __init__(
        self,
        api_key: str,
        sender_id: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
        *,
        allow_insecure_http: bool = False,
    ) -> None:
        super().__init__(
            api_key=api_key,
            sender_id=sender_id,
            base_url=base_url or self.DEFAULT_URL,
            timeout=timeout,
            allow_insecure_http=allow_insecure_http,
        )

    def _handle_http_status_error(self, exc: httpx.HTTPStatusError) -> None:
        """Map httpx.HTTPStatusError to normalized Jukto exceptions."""
        status_code = exc.response.status_code
        text = exc.response.text.strip()
        error_message = f"GreenWeb API error ({status_code}): {text or exc.response.reason_phrase}"
        logger.error("GreenWeb HTTP error [%d]: %s", status_code, text)

        if status_code in (401, 403):
            raise ProviderAuthenticationError(
                error_message,
                status_code=status_code,
                response_body=text,
                provider="GreenWeb",
            ) from exc
        elif status_code == 429:
            raise ProviderRateLimitError(
                error_message,
                status_code=status_code,
                response_body=text,
                provider="GreenWeb",
            ) from exc
        elif status_code in (400, 422):
            raise InvalidRequestError(
                error_message,
                status_code=status_code,
                response_body=text,
                provider="GreenWeb",
            ) from exc
        elif status_code >= 500:
            raise ProviderServerError(
                error_message,
                status_code=status_code,
                response_body=text,
                provider="GreenWeb",
            ) from exc
        else:
            raise ProviderError(
                error_message,
                status_code=status_code,
                response_body=text,
                provider="GreenWeb",
            ) from exc

    def _inspect_response_content(self, response: httpx.Response) -> Any:
        """Inspect GreenWeb text or JSON content for provider-specific error indicators."""
        raw_text = response.text.strip()
        lower_text = raw_text.lower()

        logger.debug("GreenWeb response content: %s", raw_text[:200])

        # GreenWeb text-based error strings (often returned with HTTP 200)
        if "invalid token" in lower_text or "token not found" in lower_text:
            logger.error("GreenWeb authentication failure: %s", raw_text)
            raise ProviderAuthenticationError(
                f"GreenWeb authentication failed: {raw_text}",
                status_code=response.status_code,
                response_body=raw_text,
                provider="GreenWeb",
            )
        if "account balance" in lower_text or "insufficient" in lower_text:
            logger.error("GreenWeb balance depleted: %s", raw_text)
            raise InsufficientBalanceError(
                f"GreenWeb balance insufficient: {raw_text}",
                status_code=response.status_code,
                response_body=raw_text,
                provider="GreenWeb",
            )
        if "invalid number" in lower_text or "invalid phone" in lower_text:
            logger.error("GreenWeb invalid recipient: %s", raw_text)
            raise InvalidRequestError(
                f"GreenWeb rejected recipient number: {raw_text}",
                status_code=response.status_code,
                response_body=raw_text,
                provider="GreenWeb",
            )

        # Parse JSON response
        try:
            data = response.json()
        except Exception:
            if "error" in lower_text:
                raise ProviderError(
                    f"GreenWeb error: {raw_text}",
                    status_code=response.status_code,
                    response_body=raw_text,
                    provider="GreenWeb",
                )
            return raw_text

        # Inspect JSON array or dictionary for error status
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
            first_item = data[0]
            if first_item.get("status") == "error":
                msg = first_item.get("message") or first_item.get("statusmsg") or "GreenWeb error"
                raise ProviderError(
                    f"GreenWeb error: {msg}",
                    status_code=response.status_code,
                    response_body=data,
                    provider="GreenWeb",
                )
        elif isinstance(data, dict):
            if data.get("status") == "error":
                msg = data.get("message") or data.get("statusmsg") or "GreenWeb error"
                raise ProviderError(
                    f"GreenWeb error: {msg}",
                    status_code=response.status_code,
                    response_body=data,
                    provider="GreenWeb",
                )

        return data

    def send_sms(self, phone_numbers: str | list[str], message: str) -> dict[str, Any] | list[Any]:
        if isinstance(phone_numbers, list):
            to_string = ",".join(phone_numbers)
        else:
            to_string = phone_numbers

        payload = {
            "token": self.api_key,
            "to": to_string,
            "message": message,
            "json": "",
        }

        masked_payload = mask_sensitive(payload)
        logger.debug("GreenWeb request to %s | payload: %s", self.base_url, masked_payload)

        try:
            with secure_http_client(self.base_url, self.timeout, self.allow_insecure_http) as client:
                response = client.post(self.base_url, data=payload)
                logger.debug("GreenWeb HTTP status: %d", response.status_code)
                response.raise_for_status()
                return self._inspect_response_content(response)
        except httpx.TimeoutException as exc:
            logger.error("GreenWeb request timeout: %s", exc)
            raise ProviderTimeoutError(
                f"Request to GreenWeb timed out: {exc}",
                provider="GreenWeb",
            ) from exc
        except httpx.HTTPStatusError as exc:
            self._handle_http_status_error(exc)
        except httpx.RequestError as exc:
            logger.error("GreenWeb network failure: %s", exc)
            raise ProviderConnectionError(
                f"Failed to connect to GreenWeb: {exc}",
                provider="GreenWeb",
            ) from exc

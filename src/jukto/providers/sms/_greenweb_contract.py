from __future__ import annotations

from typing import Any, Optional, NoReturn
from json import JSONDecodeError
import httpx
from jukto._responses import unexpected
from jukto.results import SMSBatchResult

from jukto.exceptions import InsufficientBalanceError, InvalidRequestError, ProviderAuthenticationError, ProviderError, SMSBatchError, ProviderRateLimitError, ProviderServerError
from jukto.logger import logger


class GreenWebContract:
    api_key: str
    base_url: str | None

    def _handle_http_status_error(self, exc: httpx.HTTPStatusError) -> NoReturn:
        """Map httpx.HTTPStatusError to normalized Jukto exceptions."""
        status_code = exc.response.status_code
        text = exc.response.text.strip()
        error_message = f'GreenWeb API error ({status_code}): [details withheld]'
        logger.error('provider=GreenWeb operation=handle_http_status_error event=error status=%d', status_code)

        if status_code in (401, 403):
            raise ProviderAuthenticationError(
                error_message,
                status_code=status_code,
                response_body=text,
                provider="GreenWeb",
            ) from None
        elif status_code == 429:
            raise ProviderRateLimitError(
                error_message,
                status_code=status_code,
                response_body=text,
                provider="GreenWeb",
            ) from None
        elif status_code in (400, 422):
            raise InvalidRequestError(
                error_message,
                status_code=status_code,
                response_body=text,
                provider="GreenWeb",
            ) from None
        elif status_code >= 500:
            raise ProviderServerError(
                error_message,
                status_code=status_code,
                response_body=text,
                provider="GreenWeb",
            ) from None
        else:
            raise ProviderError(
                error_message,
                status_code=status_code,
                response_body=text,
                provider="GreenWeb",
            ) from None


    def _batch_result(self, entries: list[Any], response: httpx.Response, raw: Any) -> SMSBatchResult:
        if not entries:
            raise unexpected(response, "GreenWeb", raw)
        results = SMSBatchResult(entries)
        if results.unknown_indices and not results.sent_indices and not results.failed_indices:
            raise unexpected(response, "GreenWeb", raw)
        if results.failed_indices or results.unknown_indices:
            raise SMSBatchError(
                "GreenWeb batch contains failed or unknown outcomes; inspect results before retrying",
                results=results, status_code=response.status_code,
                response_body=raw, provider="GreenWeb",
            )
        return results


    def _inspect_response_content(self, response: httpx.Response) -> Any:
        """Parse structured status first; never interpret echoed SMS content as errors."""
        logger.debug('provider=GreenWeb operation=inspect_response_content event=response')
        raw_text = response.text.strip()
        try:
            data = response.json()
        except (JSONDecodeError, UnicodeDecodeError):
            data = None
            decoded = False
        else:
            decoded = True

        if decoded:
            if isinstance(data, list):
                return self._batch_result(data, response, data)
            if isinstance(data, dict):
                # Single-object envelopes are legacy compatibility, not the manual's list schema.
                if data.get("status") in ("SENT", "FAILED"):
                    result = self._batch_result([data], response, data)
                    return data if result.sent_indices else result
                if data.get("status") == "error":
                    raise ProviderError(
                        "GreenWeb returned an error; details withheld", status_code=response.status_code,
                        response_body=data, provider="GreenWeb",
                    )
            raise unexpected(response, "GreenWeb", data)

        # A malformed JSON response must not be reclassified by embedded text phrases.
        if "json" in response.headers.get("content-type", "").lower() or raw_text.startswith(("{", "[")):
            raise unexpected(response, "GreenWeb", raw_text)
        lines = raw_text.splitlines()
        if lines and all(line.lower().startswith(("ok:", "error:")) for line in lines):
            entries = [{"status": "SENT" if line.lower().startswith("ok:") else "FAILED", "raw_text": line}
                       for line in lines]
            result = self._batch_result(entries, response, raw_text)
            return raw_text if len(lines) == 1 else result

        # Historical plain errors retained only as anchored prefixes, not whole-body substrings.
        lower = raw_text.lower()
        error_type: Optional[type[ProviderError]] = None
        if lower.startswith(("invalid token", "token not found")):
            error_type = ProviderAuthenticationError
        elif lower.startswith(("sms rate is greater than your account balance", "sms rate exceeds account balance", "insufficient balance")):
            error_type = InsufficientBalanceError
        elif lower.startswith(("invalid number", "invalid phone")):
            error_type = InvalidRequestError
        elif lower.startswith(("error", "general gateway error")):
            error_type = ProviderError
        if error_type is not None:
            raise error_type(
                "GreenWeb returned an error; details withheld", status_code=response.status_code,
                response_body=raw_text, provider="GreenWeb",
            )
        raise unexpected(response, "GreenWeb", raw_text)


    def _prepare_sms(self, phone_numbers: str | list[str], message: str) -> dict[str, Any]:
        if isinstance(phone_numbers, list):
            to_string = ",".join(phone_numbers)
        else:
            to_string = phone_numbers

        assert self.base_url is not None
        payload = {
            "token": self.api_key,
            "to": to_string,
            "message": message,
            "json": "1",
        }

        return payload

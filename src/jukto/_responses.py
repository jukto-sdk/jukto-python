"""Narrow response decoding and schema guards; never catch programming errors."""
from __future__ import annotations

from json import JSONDecodeError
from typing import Any
import httpx
from jukto.exceptions import UnexpectedProviderResponseError


def unexpected(response: httpx.Response, provider: str, body: Any) -> UnexpectedProviderResponseError:
    return UnexpectedProviderResponseError(
        'Provider returned an unrecognized response; details withheld',
        status_code=response.status_code, response_body=body, provider=provider,
    )


def decode_json(response: httpx.Response, provider: str) -> Any:
    try:
        return response.json()
    except (JSONDecodeError, UnicodeDecodeError):
        raise unexpected(response, provider, response.text) from None


def error_body(response: httpx.Response) -> Any:
    """Retain error evidence without assuming the JSON envelope is an object."""
    try:
        return response.json()
    except (JSONDecodeError, UnicodeDecodeError):
        return response.text


def require_object(data: Any, response: httpx.Response, provider: str) -> dict[str, Any]:
    if not isinstance(data, dict) or not data:
        raise unexpected(response, provider, data)
    return data

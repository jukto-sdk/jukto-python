"""Credential transport policy shared by synchronous adapters."""
from __future__ import annotations

import httpx
from jukto.exceptions import JuktoConfigurationError


def validate_endpoint(url: str, allow_insecure_http: bool = False) -> None:
    try:
        parsed = httpx.URL(url)
    except (httpx.InvalidURL, TypeError):
        raise JuktoConfigurationError('Provider endpoint must be an absolute HTTPS URL') from None
    if not parsed.host or parsed.scheme not in ('https', 'http'):
        raise JuktoConfigurationError('Provider endpoint must be an absolute HTTP(S) URL')
    if parsed.userinfo:
        raise JuktoConfigurationError('Provider endpoint must not contain URL credentials')
    if parsed.scheme == 'http' and not allow_insecure_http:
        raise JuktoConfigurationError(
            'Cleartext provider endpoints are disabled. Use HTTPS or explicitly set '
            'allow_insecure_http=True for legacy/local use; credentials will be unencrypted.'
        )


def secure_http_client(url: str, timeout: float, allow_insecure_http: bool = False) -> httpx.Client:
    # Recheck the actual target, including after public base_url mutation.
    validate_endpoint(url, allow_insecure_http)
    return httpx.Client(timeout=timeout, verify=True, follow_redirects=False)

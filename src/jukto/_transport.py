"""Credential transport policy shared by synchronous adapters."""
from __future__ import annotations

import asyncio
import httpx
from threading import RLock
from typing import Any
from jukto.exceptions import JuktoConfigurationError
from jukto._operations import before_request, after_response


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


class SyncTransport:
    """One lazy owned pool or one borrowed client; provider parsing stays in adapters."""

    def __init__(self, *, timeout: float | httpx.Timeout = 30.0,
                 limits: httpx.Limits | None = None,
                 http_client: httpx.Client | None = None,
                 allow_insecure_http: bool = False) -> None:
        if http_client is not None and not isinstance(http_client, httpx.Client):
            raise JuktoConfigurationError('http_client must be a synchronous httpx.Client')
        if http_client is not None and limits is not None:
            raise JuktoConfigurationError('Configure limits on the borrowed http_client, not the provider')
        if limits is not None and not isinstance(limits, httpx.Limits):
            raise JuktoConfigurationError('limits must be httpx.Limits')
        try:
            self.timeout = httpx.Timeout(timeout)
        except (TypeError, ValueError):
            raise JuktoConfigurationError('timeout must be an HTTPX-compatible timeout') from None
        self.limits = limits if limits is not None else httpx.Limits()
        self.allow_insecure_http = allow_insecure_http
        self._client = http_client
        self._owned = http_client is None
        self._closed = False
        self._lock = RLock()

    def ensure_open(self) -> None:
        with self._lock:
            if self._closed or (self._client is not None and self._client.is_closed):
                raise JuktoConfigurationError('Provider HTTP client is closed')

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        validate_endpoint(url, self.allow_insecure_http)
        with self._lock:
            self.ensure_open()
            if self._client is None:
                self._client = httpx.Client(timeout=self.timeout, limits=self.limits,
                                            verify=True, follow_redirects=False)
            client = self._client
        # Override borrowed redirect/auth defaults; never add automatic retries.
        kwargs['follow_redirects'] = False
        kwargs['timeout'] = self.timeout
        kwargs['auth'] = None
        before_request(method, url)
        response = client.request(method, url, **kwargs)
        after_response(response)
        return response

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            if self._owned and self._client is not None:
                self._client.close()


class TransportLifecycle:
    """Lifecycle surface shared by synchronous provider contracts."""
    _transport: SyncTransport

    def close(self) -> None:
        self._transport.close()

    def __enter__(self):
        self._transport.ensure_open()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()


class AsyncTransport:
    """Asyncio-scoped owned or borrowed pool. Close after in-flight work finishes."""

    def __init__(self, *, timeout: float | httpx.Timeout = 30.0,
                 limits: httpx.Limits | None = None,
                 http_client: httpx.AsyncClient | None = None,
                 allow_insecure_http: bool = False) -> None:
        if http_client is not None and not isinstance(http_client, httpx.AsyncClient):
            raise JuktoConfigurationError('http_client must be a synchronous httpx.AsyncClient')
        if http_client is not None and limits is not None:
            raise JuktoConfigurationError('Configure limits on the borrowed http_client, not the provider')
        if limits is not None and not isinstance(limits, httpx.Limits):
            raise JuktoConfigurationError('limits must be httpx.Limits')
        try:
            self.timeout = httpx.Timeout(timeout)
        except (TypeError, ValueError):
            raise JuktoConfigurationError('timeout must be an HTTPX-compatible timeout') from None
        self.limits = limits if limits is not None else httpx.Limits()
        self.allow_insecure_http = allow_insecure_http
        self._client = http_client
        self._owned = http_client is None
        self._closed = False
        self._closing: asyncio.Task[None] | None = None

    def ensure_open(self) -> None:
        if self._closed or (self._client is not None and self._client.is_closed):
            raise JuktoConfigurationError('Provider HTTP client is closed')

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        validate_endpoint(url, self.allow_insecure_http)
        self.ensure_open()
        # No suspension between checking and publishing the lazy pool.
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout, limits=self.limits,
                                            verify=True, follow_redirects=False)
        kwargs['follow_redirects'] = False
        kwargs['timeout'] = self.timeout
        kwargs['auth'] = None
        before_request(method, url)
        response = await self._client.request(method, url, **kwargs)
        after_response(response)
        return response

    async def aclose(self) -> None:
        self._closed = True
        if not self._owned or self._client is None:
            return
        if self._closing is None:
            self._closing = asyncio.create_task(self._client.aclose())
        # Shield cleanup, including repeated cancellation, but await its completion.
        cancelled = False
        while not self._closing.done():
            try:
                await asyncio.shield(self._closing)
            except asyncio.CancelledError:
                cancelled = True
        self._closing.result()
        if cancelled:
            raise asyncio.CancelledError


class AsyncTransportLifecycle:
    _transport: AsyncTransport

    async def aclose(self) -> None:
        await self._transport.aclose()

    async def __aenter__(self):
        self._transport.ensure_open()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        await self.aclose()

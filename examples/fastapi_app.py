"""Application-owned sync provider; blocking operations run in FastAPI's thread pool."""
from __future__ import annotations
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from jukto import BaseSMSProvider
from examples.application import alpha_from_environment, notify


def get_provider(request: Request) -> BaseSMSProvider:
    return request.app.state.sms_provider


def create_app(factory: Callable[[], BaseSMSProvider] = alpha_from_environment) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        provider = factory()  # Construction is lazy: it does not perform HTTP.
        app.state.sms_provider = provider
        try:
            yield
        finally:
            await run_in_threadpool(provider.close)

    app = FastAPI(lifespan=lifespan)

    @app.post("/sms")
    def submit(payload: dict[str, Any], provider: BaseSMSProvider = Depends(get_provider)) -> JSONResponse:
        # A normal def route runs in a worker thread; never call this sync SDK
        # directly inside an async def request handler on the event loop.
        body, status = notify(provider, payload)
        return JSONResponse(body, status_code=status)

    return app


app = create_app()  # No credentials are read until lifespan startup.

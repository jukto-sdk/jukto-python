"""One native async provider per asyncio worker; bound in-flight submissions."""
from __future__ import annotations
import asyncio
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from jukto import AsyncAlphaSMSClient, AsyncBaseSMSProvider, JuktoConfigurationError, JuktoError, SMSBatchError
from examples.application import safe_result


def configured_provider() -> AsyncBaseSMSProvider:
    key = os.environ.get('JUKTO_ALPHA_API_KEY', '')
    if not key.strip():
        raise JuktoConfigurationError('Configure JUKTO_ALPHA_API_KEY before serving requests')
    return AsyncAlphaSMSClient(key, timeout=10.0)


def get_provider(request: Request) -> AsyncBaseSMSProvider:
    return request.app.state.sms_provider


def create_app(factory: Callable[[], AsyncBaseSMSProvider] = configured_provider,
               max_in_flight: int = 10) -> FastAPI:
    if type(max_in_flight) is not int or max_in_flight <= 0:
        raise ValueError('max_in_flight must be a positive integer')

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with factory() as provider:
            app.state.sms_provider = provider
            app.state.sms_limit = asyncio.Semaphore(max_in_flight)
            yield

    app = FastAPI(lifespan=lifespan)

    @app.post('/sms')
    async def submit(request: Request, payload: dict[str, Any],
                     provider: AsyncBaseSMSProvider = Depends(get_provider)) -> JSONResponse:
        if any(not isinstance(payload.get(key), str) or not payload[key].strip() for key in ('phone', 'message')):
            return JSONResponse({'error': 'phone and message must be nonempty strings'}, status_code=400)
        try:
            async with request.app.state.sms_limit:
                result = await provider.submit_sms(payload['phone'], payload['message'])
        except SMSBatchError as error:
            if error.normalized_result is not None:
                return JSONResponse(safe_result(error.normalized_result), status_code=202)
            return JSONResponse({'error': 'batch_result_unavailable', 'status': 'unknown',
                                 'reconciliation_required': True}, status_code=502)
        except JuktoError as error:
            return JSONResponse({'error': 'provider_error', 'status': error.outcome.value,
                                 'reconciliation_required': error.reconciliation_required}, status_code=502)
        return JSONResponse(safe_result(result), status_code=202)

    return app


app = create_app()

"""Request-local evidence for error metadata; never infer a successful side effect."""
from __future__ import annotations
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Optional, TypeVar, cast
import httpx
from jukto.exceptions import ProviderError, SMSBatchError
from jukto.results import Outcome, sms_submission
from jukto._responses import error_body

@dataclass
class RequestEvidence:
    response: Optional[httpx.Response] = None
    attempted: bool = False

_evidence: ContextVar[Optional[RequestEvidence]] = ContextVar('jukto_request_evidence', default=None)
F = TypeVar('F', bound=Callable[..., Any])

def operation(function: F) -> F:
    @wraps(function)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        evidence = RequestEvidence()
        token = _evidence.set(evidence)
        try:
            return function(*args, **kwargs)
        except ProviderError as exc:
            annotate_error(exc, evidence)
            raise
        finally:
            _evidence.reset(token)
    return cast(F, wrapped)


def before_request(method: str, url: str) -> None:
    evidence = _evidence.get()
    if evidence is not None:
        evidence.response = None
        # Auth is not a shipment/SMS side effect; transport retry policy is unchanged.
        if method.upper() == 'POST' and not url.endswith('/issue-token'):
            evidence.attempted = True


def after_response(response: httpx.Response) -> None:
    evidence = _evidence.get()
    if evidence is not None: evidence.response = response


def annotate_error(exc: ProviderError, evidence: RequestEvidence) -> None:
    response = evidence.response
    exc.http_status = response.status_code if response is not None else None
    if response is not None:
        exc.request_id = response.headers.get('X-Request-ID')
        exc.retry_after = response.headers.get('Retry-After')
    body = exc.response_body
    if not isinstance(body, dict) and response is not None:
        body = error_body(response)
    if isinstance(body, dict):
        field = {'AlphaSMS':'error', 'BulkSMSBD':'response_code', 'Steadfast':'status', 'RedX':'status'}.get(exc.provider or '')
        if field is not None:
            code = body.get(field)
            if type(code) in (str, int): exc.provider_error_code = code
    exc.outcome = Outcome.UNKNOWN
    exc.reconciliation_required = evidence.attempted
    # Published AlphaSMS rejection codes establish submission failure;
    # its server-error code 409 and unknown codes do not.
    if exc.provider == 'AlphaSMS' and exc.http_status == 200 and exc.provider_error_code in (400, 403, 404, 405, 410, 411, 412, 413, 414, 415, 416, 417, 420,
                                                                  '400', '403', '404', '405', '410', '411', '412', '413', '414', '415', '416', '417', '420'):
        exc.outcome = Outcome.FAILED
        exc.reconciliation_required = False
    if isinstance(exc, SMSBatchError):
        exc.normalized_result = sms_submission('GreenWeb', exc.results)
        exc.outcome = exc.normalized_result.status
        exc.reconciliation_required = any(r.status == Outcome.UNKNOWN for r in exc.normalized_result.recipients)


def async_operation(function: F) -> F:
    @wraps(function)
    async def wrapped(*args: Any, **kwargs: Any) -> Any:
        evidence = RequestEvidence()
        token = _evidence.set(evidence)
        try:
            return await function(*args, **kwargs)
        except ProviderError as exc:
            annotate_error(exc, evidence)
            raise
        finally:
            _evidence.reset(token)
    return cast(F, wrapped)

"""Suppress HTTPX's credential-bearing URL in payment-request log records only."""

from contextlib import contextmanager
from contextvars import ContextVar
import logging
from typing import Iterator

_payment_request: ContextVar[bool] = ContextVar(
    "jukto_payment_httpx_log", default=False
)


class _PaymentURLFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if _payment_request.get():
            # HTTPX's INFO request record includes the full GET query/password.
            # Do not depend on its formatting/argument order or retain secret args.
            record.msg = "provider=SSLCommerz event=http_client details=withheld"
            record.args = ()
            record.exc_info = None
            record.exc_text = None
            record.stack_info = None
        return True


logging.getLogger("httpx").addFilter(_PaymentURLFilter())


@contextmanager
def safe_httpx_logs() -> Iterator[None]:
    token = _payment_request.set(True)
    try:
        yield
    finally:
        _payment_request.reset(token)

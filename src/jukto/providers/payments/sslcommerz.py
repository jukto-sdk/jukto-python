"""SSLCOMMERZ hosted BDT checkout; no implicit payment or refund replay."""

from __future__ import annotations
from typing import Any, Mapping
import httpx
from jukto._transport import SyncTransport, validate_endpoint
from jukto._operations import operation, before_request
from jukto.exceptions import (
    JuktoConfigurationError,
    ProviderTimeoutError,
    ProviderConnectionError,
)
from jukto.interfaces.payments import BasePaymentProvider
from jukto.payments import (
    PaymentRequest,
    PaymentReference,
    PaymentInitiationResult,
    PaymentVerificationResult,
    PaymentQueryResult,
    RefundRequest,
    RefundResult,
    text,
)
from ._sslcommerz_contract import SSLCommerzContract
from ._logging import safe_httpx_logs


class SSLCommerzClient(SSLCommerzContract, BasePaymentProvider):
    def __init__(
        self,
        store_id: str,
        store_password: str,
        *,
        sandbox: bool = True,
        timeout: float | httpx.Timeout = 30.0,
        http_client: httpx.Client | None = None,
        limits: httpx.Limits | None = None,
    ) -> None:
        for value in (store_id, store_password):
            if not isinstance(value, str) or not value.strip() or len(value) > 30:
                raise JuktoConfigurationError(
                    "SSLCommerz requires nonempty store credentials of at most 30 characters"
                )
        if type(sandbox) is not bool:
            raise JuktoConfigurationError("sandbox must be a boolean")
        self.store_id, self.store_password = store_id, store_password
        self.base_url = (
            "https://sandbox.sslcommerz.com"
            if sandbox
            else "https://securepay.sslcommerz.com"
        )
        validate_endpoint(self.base_url)
        self._transport = SyncTransport(
            timeout=timeout, http_client=http_client, limits=limits
        )

    def _request(
        self, method: str, path: str, *, side_effect: bool = False, **kwargs: Any
    ) -> httpx.Response:
        self._transport.ensure_open()
        if side_effect:
            # Provider refund initiation is GET but still changes financial state.
            before_request("POST", self.base_url + path)
        try:
            with safe_httpx_logs():
                return self._transport.request(
                    method,
                    self.base_url + path,
                    headers={"Cache-Control": "no-store"},
                    **kwargs,
                )
        except httpx.TimeoutException:
            raise ProviderTimeoutError(
                "SSLCommerz request timed out; details withheld",
                provider=self.provider_name,
            ) from None
        except httpx.RequestError:
            raise ProviderConnectionError(
                "SSLCommerz connection failed; details withheld",
                provider=self.provider_name,
            ) from None

    @operation
    def initiate(self, request: PaymentRequest) -> PaymentInitiationResult:
        payload = self._prepare_initiation(request)
        return self._initiation(
            self._request("POST", self.INITIATE, data=payload), request.reference
        )

    @operation
    def verify(
        self, validation_id: str, expected: PaymentReference
    ) -> PaymentVerificationResult:
        text(validation_id, "validation_id", 50)
        response = self._request(
            "GET", self.VALIDATE, params=dict(self._credentials(), val_id=validation_id)
        )
        return self._validated(response, expected, validation_id)

    @operation
    def query_transaction(self, expected: PaymentReference) -> PaymentQueryResult:
        response = self._request(
            "GET",
            self.TRANSACTION,
            params=dict(self._credentials(), tran_id=expected.merchant_transaction_id),
        )
        return self._query(response, expected)

    @operation
    def query_session(
        self, session_id: str, expected: PaymentReference
    ) -> PaymentVerificationResult:
        text(session_id, "session_id", 50)
        response = self._request(
            "GET",
            self.TRANSACTION,
            params=dict(self._credentials(), sessionkey=session_id),
        )
        return self._session(response, expected, session_id)

    def verify_notification(
        self, notification: Mapping[str, str], expected: PaymentReference
    ) -> PaymentVerificationResult | PaymentQueryResult:
        validation_id = self._notification(notification, expected)
        return (
            self.verify(validation_id, expected)
            if validation_id is not None
            else self.query_transaction(expected)
        )

    @operation
    def refund(self, request: RefundRequest) -> RefundResult:
        payload = self._refund_payload(request)
        response = self._request(
            "GET", self.TRANSACTION, params=payload, side_effect=True
        )
        return self._refund(response, request.bank_transaction_id, None, request)

    @operation
    def query_refund(
        self, provider_refund_id: str, bank_transaction_id: str
    ) -> RefundResult:
        text(provider_refund_id, "provider_refund_id", 50)
        text(bank_transaction_id, "bank_transaction_id", 80)
        response = self._request(
            "GET",
            self.TRANSACTION,
            params=dict(self._credentials(), refund_ref_id=provider_refund_id),
        )
        return self._refund(response, bank_transaction_id, provider_refund_id)

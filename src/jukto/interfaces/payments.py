"""Payment contracts separate hosted initiation, verification and refunds."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Mapping
from jukto.payments import (
    PaymentRequest,
    PaymentReference,
    PaymentInitiationResult,
    PaymentVerificationResult,
    PaymentQueryResult,
    RefundRequest,
    RefundResult,
    PaymentCapabilities,
)
from jukto._transport import TransportLifecycle, AsyncTransportLifecycle


class BasePaymentProvider(TransportLifecycle, ABC):
    capabilities: PaymentCapabilities

    @abstractmethod
    def initiate(self, request: PaymentRequest) -> PaymentInitiationResult: ...
    @abstractmethod
    def verify(
        self, validation_id: str, expected: PaymentReference
    ) -> PaymentVerificationResult: ...
    @abstractmethod
    def query_transaction(self, expected: PaymentReference) -> PaymentQueryResult: ...
    @abstractmethod
    def query_session(
        self, session_id: str, expected: PaymentReference
    ) -> PaymentVerificationResult: ...
    @abstractmethod
    def verify_notification(
        self, notification: Mapping[str, str], expected: PaymentReference
    ) -> PaymentVerificationResult | PaymentQueryResult: ...
    @abstractmethod
    def refund(self, request: RefundRequest) -> RefundResult: ...
    @abstractmethod
    def query_refund(
        self, provider_refund_id: str, bank_transaction_id: str
    ) -> RefundResult: ...


class AsyncBasePaymentProvider(AsyncTransportLifecycle, ABC):
    capabilities: PaymentCapabilities

    @abstractmethod
    async def initiate(self, request: PaymentRequest) -> PaymentInitiationResult: ...
    @abstractmethod
    async def verify(
        self, validation_id: str, expected: PaymentReference
    ) -> PaymentVerificationResult: ...
    @abstractmethod
    async def query_transaction(
        self, expected: PaymentReference
    ) -> PaymentQueryResult: ...
    @abstractmethod
    async def query_session(
        self, session_id: str, expected: PaymentReference
    ) -> PaymentVerificationResult: ...
    @abstractmethod
    async def verify_notification(
        self, notification: Mapping[str, str], expected: PaymentReference
    ) -> PaymentVerificationResult | PaymentQueryResult: ...
    @abstractmethod
    async def refund(self, request: RefundRequest) -> RefundResult: ...
    @abstractmethod
    async def query_refund(
        self, provider_refund_id: str, bank_transaction_id: str
    ) -> RefundResult: ...

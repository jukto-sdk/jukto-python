"""Typed hosted payment domain. Results retain sensitive raw evidence explicitly."""

from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any
from jukto.exceptions import JuktoValidationError, ProviderError
from jukto._transport import validate_endpoint


class PaymentStatus(str, Enum):
    REQUIRES_ACTION = "requires_action"
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class RefundStatus(str, Enum):
    PENDING = "pending"
    REFUNDED = "refunded"
    FAILED = "failed"
    UNKNOWN = "unknown"


class PaymentVerificationError(ProviderError):
    """Notification or authenticated response does not match trusted payment data."""


def text(value: str, field_name: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise JuktoValidationError(
            f"{field_name} must be a nonempty string within its documented length",
            provider="SSLCommerz",
        )
    return value


def amount(value: Decimal) -> str:
    # Reject floats, silent rounding and context-dependent quantization.
    if (
        not isinstance(value, Decimal)
        or not value.is_finite()
        or value <= 0
        or value > Decimal("99999999.99")
    ):
        raise JuktoValidationError(
            "amount must be a finite positive Decimal within decimal(10,2)",
            provider="SSLCommerz",
        )
    digits = value.as_tuple()
    exponent = digits.exponent
    if (
        isinstance(exponent, int)
        and exponent < -2
        and any(digits.digits[exponent + 2 :])
    ):
        raise JuktoValidationError(
            "amount must have at most two fractional digits", provider="SSLCommerz"
        )
    return format(value, ".2f")


@dataclass(frozen=True)
class PaymentReference:
    merchant_transaction_id: str
    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        text(self.merchant_transaction_id, "merchant_transaction_id", 30)
        amount(self.amount)
        if self.currency != "BDT":
            raise JuktoValidationError(
                "This integration currently supports explicit BDT only",
                provider="SSLCommerz",
            )


@dataclass(frozen=True)
class PaymentCustomer:
    name: str
    email: str
    phone: str
    address: str
    city: str
    postcode: str
    country: str


@dataclass(frozen=True)
class PaymentURLs:
    success: str
    failure: str
    cancel: str
    ipn: str

    def __post_init__(self) -> None:
        for value in (self.success, self.failure, self.cancel, self.ipn):
            text(value, "callback URL", 255)
            validate_endpoint(value)


@dataclass(frozen=True)
class PaymentRequest:
    reference: PaymentReference
    customer: PaymentCustomer
    urls: PaymentURLs
    product_name: str
    product_category: str


@dataclass(frozen=True)
class PaymentInitiationResult:
    reference: PaymentReference
    status: PaymentStatus
    session_id: str | None = None
    customer_action_url: str | None = field(default=None, repr=False)
    provider_status: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def reconciliation_required(self) -> bool:
        return self.status == PaymentStatus.UNKNOWN


@dataclass(frozen=True)
class PaymentVerificationResult:
    reference: PaymentReference
    status: PaymentStatus
    validation_id: str | None = None
    bank_transaction_id: str | None = None
    requires_review: bool = True
    provider_status: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def can_fulfill(self) -> bool:
        return self.status == PaymentStatus.PAID and not self.requires_review

    @property
    def reconciliation_required(self) -> bool:
        return self.status in (PaymentStatus.UNKNOWN, PaymentStatus.PENDING)


@dataclass(frozen=True)
class PaymentQueryResult:
    reference: PaymentReference
    attempts: tuple[PaymentVerificationResult, ...]
    raw: dict[str, Any] = field(default_factory=dict, repr=False)
    # Empty/multiple attempts are evidence; never choose a winner implicitly.


@dataclass(frozen=True)
class RefundRequest:
    payment: PaymentReference
    bank_transaction_id: str
    merchant_refund_id: str
    amount: Decimal
    remarks: str

    def __post_init__(self) -> None:
        text(self.bank_transaction_id, "bank_transaction_id", 80)
        text(self.merchant_refund_id, "merchant_refund_id", 30)
        text(self.remarks, "remarks", 255)
        amount(self.amount)
        if self.amount > self.payment.amount:
            raise JuktoValidationError(
                "Refund exceeds the original payment amount", provider="SSLCommerz"
            )


@dataclass(frozen=True)
class RefundResult:
    bank_transaction_id: str
    status: RefundStatus
    provider_refund_id: str | None
    merchant_refund_id: str | None = None
    requested_amount: Decimal | None = None
    provider_status: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)
    currency: str | None = None
    merchant_transaction_id: str | None = None

    @property
    def reconciliation_required(self) -> bool:
        return self.status in (RefundStatus.PENDING, RefundStatus.UNKNOWN)


@dataclass(frozen=True)
class PaymentCapabilities:
    hosted_checkout: bool = True
    server_verification: bool = True
    notification_verification: bool = True
    transaction_query: bool = True
    partial_refund: bool = True
    refund_query: bool = True
    separate_execution: bool = False
    provider_enforced_idempotency: bool | None = (
        None  # Unverified; references are not guarantees.
    )
    supported_currencies: tuple[str, ...] = ("BDT",)

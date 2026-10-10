"""SSLCOMMERZ v4 hosted BDT contract; provenance: docs/payment-contracts.md."""

from __future__ import annotations
from decimal import Decimal, InvalidOperation
from hashlib import md5
from hmac import compare_digest
from typing import Any, Mapping
from urllib.parse import parse_qsl
import re
import httpx
from jukto._responses import decode_json, require_object, unexpected, error_body
from jukto.exceptions import (
    ProviderError,
    ProviderAuthenticationError,
    InvalidRequestError,
    ProviderServerError,
    ProviderRateLimitError,
    JuktoConfigurationError,
)
from jukto._transport import validate_endpoint
from jukto.payments import (
    PaymentReference,
    PaymentRequest,
    PaymentInitiationResult,
    PaymentVerificationResult,
    PaymentQueryResult,
    PaymentStatus,
    RefundRequest,
    RefundResult,
    RefundStatus,
    PaymentVerificationError,
    PaymentCapabilities,
    text,
    amount,
)


class SSLCommerzContract:
    store_id: str
    store_password: str
    base_url: str
    provider_name = "SSLCommerz"
    capabilities = PaymentCapabilities()
    INITIATE = "/gwprocess/v4/api.php"
    VALIDATE = "/validator/api/validationserverAPI.php"
    TRANSACTION = "/validator/api/merchantTransIDvalidationAPI.php"

    @staticmethod
    def parse_notification(body: bytes) -> dict[str, str]:
        """Decode a bounded UTF-8 form, rejecting duplicate keys before dict collapse."""
        if not isinstance(body, bytes) or len(body) > 65536:
            raise PaymentVerificationError(
                "SSLCommerz notification body exceeds supported form limits",
                provider="SSLCommerz",
            )
        try:
            pairs = parse_qsl(
                body.decode("utf-8"),
                keep_blank_values=True,
                strict_parsing=True,
                encoding="utf-8",
                errors="strict",
                max_num_fields=128,
            )
        except (UnicodeDecodeError, ValueError):
            raise PaymentVerificationError(
                "SSLCommerz notification is not a valid UTF-8 form",
                provider="SSLCommerz",
            ) from None
        if len({key for key, value in pairs}) != len(pairs):
            raise PaymentVerificationError(
                "SSLCommerz notification contains duplicate form keys",
                provider="SSLCommerz",
            )
        return dict(pairs)

    def _credentials(self) -> dict[str, str]:
        return {
            "store_id": self.store_id,
            "store_passwd": self.store_password,
            "format": "json",
        }

    def _prepare_initiation(self, request: PaymentRequest) -> dict[str, str]:
        if not Decimal("10.00") <= request.reference.amount <= Decimal("500000.00"):
            from jukto.exceptions import JuktoValidationError

            raise JuktoValidationError(
                "BDT checkout amount must be between 10.00 and 500000.00",
                provider=self.provider_name,
            )
        customer = request.customer
        fields = {
            "cus_name": (customer.name, 50),
            "cus_email": (customer.email, 50),
            "cus_phone": (customer.phone, 20),
            "cus_add1": (customer.address, 50),
            "cus_city": (customer.city, 50),
            "cus_postcode": (customer.postcode, 30),
            "cus_country": (customer.country, 50),
            "product_name": (request.product_name, 255),
            "product_category": (request.product_category, 50),
        }
        payload = {
            key: text(value, key, limit) for key, (value, limit) in fields.items()
        }
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", customer.email):
            from jukto.exceptions import JuktoValidationError

            raise JuktoValidationError(
                "cus_email must be an email address", provider=self.provider_name
            )
        payload.update(self._credentials())
        payload.update(
            tran_id=request.reference.merchant_transaction_id,
            total_amount=amount(request.reference.amount),
            currency=request.reference.currency,
            success_url=request.urls.success,
            fail_url=request.urls.failure,
            cancel_url=request.urls.cancel,
            ipn_url=request.urls.ipn,
            shipping_method="NO",
            product_profile="non-physical-goods",
            num_of_item="1",
            emi_option="0",
        )
        return payload

    def _http_error(self, response: httpx.Response) -> None:
        code = response.status_code
        if response.is_success:
            return
        cls = (
            ProviderAuthenticationError
            if code in (401, 403)
            else InvalidRequestError
            if code in (400, 422)
            else ProviderRateLimitError
            if code == 429
            else ProviderServerError
            if code >= 500
            else ProviderError
        )
        raise cls(
            "SSLCommerz HTTP request failed; details withheld",
            status_code=code,
            response_body=error_body(response),
            provider=self.provider_name,
        ) from None

    def _data(self, response: httpx.Response) -> dict[str, Any]:
        self._http_error(response)
        data = require_object(
            decode_json(response, self.provider_name), response, self.provider_name
        )
        connect = data.get("APIConnect")
        if connect in ("FAILED", "INACTIVE", "INVALID_REQUEST"):
            cls = (
                InvalidRequestError
                if connect == "INVALID_REQUEST"
                else ProviderAuthenticationError
            )
            raise cls(
                "SSLCommerz rejected the API request; details withheld",
                provider=self.provider_name,
                provider_error_code=connect,
                response_body=data,
            )
        if connect is not None and connect != "DONE":
            raise unexpected(response, self.provider_name, data)
        return data

    def _initiation(
        self, response: httpx.Response, reference: PaymentReference
    ) -> PaymentInitiationResult:
        data = self._data(response)
        status = data.get("status")
        if status == "FAILED":
            return PaymentInitiationResult(
                reference, PaymentStatus.FAILED, provider_status=status, raw=data
            )
        if status != "SUCCESS":
            raise unexpected(response, self.provider_name, data)
        session, url = data.get("sessionkey"), data.get("GatewayPageURL")
        if not isinstance(session, str) or not session or not isinstance(url, str):
            raise unexpected(response, self.provider_name, data)
        try:
            validate_endpoint(url)
        except JuktoConfigurationError:
            raise unexpected(response, self.provider_name, data) from None
        if httpx.URL(url).host != httpx.URL(self.base_url).host or httpx.URL(
            url
        ).port not in (None, 443):
            raise unexpected(response, self.provider_name, data)
        return PaymentInitiationResult(
            reference, PaymentStatus.REQUIRES_ACTION, session, url, status, data
        )

    def _verification(
        self,
        data: dict[str, Any],
        response: httpx.Response,
        reference: PaymentReference,
        validation_id: str | None = None,
    ) -> PaymentVerificationResult:
        status = data.get("status")
        if not isinstance(status, str) or not status:
            raise unexpected(response, self.provider_name, data)
        if status == "INVALID_TRANSACTION":
            raise PaymentVerificationError(
                "SSLCommerz validation ID is invalid; payment outcome remains unknown",
                provider=self.provider_name,
                provider_error_code=status,
                response_body=data,
            )
        if data.get("tran_id") != reference.merchant_transaction_id:
            raise PaymentVerificationError(
                "SSLCommerz transaction does not match stored payment",
                provider=self.provider_name,
                response_body=data,
            )
        # BDT only: compare both transaction/settlement fields, never net store_amount.
        for key in ("currency", "currency_type"):
            if data.get(key) != reference.currency:
                raise PaymentVerificationError(
                    "SSLCommerz currency does not match stored payment",
                    provider=self.provider_name,
                    response_body=data,
                )
        for key in ("amount", "currency_amount"):
            value = data.get(key)
            if not isinstance(value, (str, int)) or isinstance(value, bool):
                raise unexpected(response, self.provider_name, data)
            try:
                parsed = Decimal(value)
            except InvalidOperation:
                raise unexpected(response, self.provider_name, data) from None
            if not parsed.is_finite() or parsed != reference.amount:
                raise PaymentVerificationError(
                    "SSLCommerz amount does not match stored payment",
                    provider=self.provider_name,
                    response_body=data,
                )
        if "store_id" in data and data["store_id"] != self.store_id:
            raise PaymentVerificationError(
                "SSLCommerz store does not match configured merchant",
                provider=self.provider_name,
                response_body=data,
            )
        state = {
            "VALID": PaymentStatus.PAID,
            "VALIDATED": PaymentStatus.PAID,
            "PENDING": PaymentStatus.PENDING,
            "FAILED": PaymentStatus.FAILED,
        }.get(status, PaymentStatus.UNKNOWN)
        val, bank = data.get("val_id"), data.get("bank_tran_id")
        if state == PaymentStatus.PAID:
            if (
                not isinstance(val, str)
                or not val
                or not isinstance(bank, str)
                or not bank
            ):
                raise unexpected(response, self.provider_name, data)
            if validation_id is not None and val != validation_id:
                raise PaymentVerificationError(
                    "SSLCommerz validation ID does not match requested payment",
                    provider=self.provider_name,
                    response_body=data,
                )
        risk = data.get("risk_level")
        safe = (type(risk) is int and risk == 0) or (
            isinstance(risk, str) and risk == "0"
        )
        return PaymentVerificationResult(
            reference,
            state,
            val if isinstance(val, str) else None,
            bank if isinstance(bank, str) else None,
            not safe,
            status,
            data,
        )

    def _validated(
        self, response: httpx.Response, reference: PaymentReference, val_id: str
    ) -> PaymentVerificationResult:
        return self._verification(self._data(response), response, reference, val_id)

    def _session(
        self, response: httpx.Response, reference: PaymentReference, session_id: str
    ) -> PaymentVerificationResult:
        data = self._data(response)
        if data.get("APIConnect") != "DONE" or data.get("sessionkey") != session_id:
            raise unexpected(response, self.provider_name, data)
        return self._verification(data, response, reference)

    def _query(
        self, response: httpx.Response, reference: PaymentReference
    ) -> PaymentQueryResult:
        data = self._data(response)
        entries, count = data.get("element"), data.get("no_of_trans_found")
        if (
            data.get("APIConnect") != "DONE"
            or not isinstance(entries, list)
            or type(count) is not int
            or count != len(entries)
        ):
            raise unexpected(response, self.provider_name, data)
        if any(not isinstance(entry, dict) for entry in entries):
            raise unexpected(response, self.provider_name, data)
        return PaymentQueryResult(
            reference,
            tuple(self._verification(entry, response, reference) for entry in entries),
            data,
        )

    def _notification(
        self, notification: Mapping[str, str], reference: PaymentReference
    ) -> str | None:
        """Verify official MD5 parameter signature; require all decision fields signed."""
        if not isinstance(notification, Mapping) or any(
            not isinstance(k, str) or not isinstance(v, str)
            for k, v in notification.items()
        ):
            raise PaymentVerificationError(
                "SSLCommerz notification must contain single string values",
                provider=self.provider_name,
            )
        keys = notification.get("verify_key", "").split(",")
        required = {
            "tran_id",
            "amount",
            "currency",
            "currency_type",
            "currency_amount",
            "status",
            "store_id",
        }
        if (
            len(keys) != len(set(keys))
            or not required.issubset(keys)
            or any(
                not re.fullmatch(r"[A-Za-z0-9_]+", key) or key not in notification
                for key in keys
            )
            or set(keys)
            & {"store_passwd", "verify_key", "verify_sign", "verify_sign_sha2"}
        ):
            raise PaymentVerificationError(
                "SSLCommerz notification has incomplete signed fields",
                provider=self.provider_name,
            )
        if notification.get("status") in ("VALID", "VALIDATED") and not {
            "val_id",
            "bank_tran_id",
        }.issubset(keys):
            raise PaymentVerificationError(
                "SSLCommerz validation ID must be signed", provider=self.provider_name
            )
        fields = {key: notification[key] for key in keys}
        fields["store_passwd"] = md5(self.store_password.encode()).hexdigest()
        canonical = "&".join(f"{key}={fields[key]}" for key in sorted(fields))
        signature = notification.get("verify_sign", "")
        if not re.fullmatch("[0-9a-f]{32}", signature) or not compare_digest(
            md5(canonical.encode()).hexdigest(), signature
        ):
            raise PaymentVerificationError(
                "SSLCommerz notification signature is invalid",
                provider=self.provider_name,
            )
        if notification.get("store_id") != self.store_id:
            raise PaymentVerificationError(
                "SSLCommerz notification store does not match",
                provider=self.provider_name,
            )
        # Compare callback identity/amount too, but only a server response can fulfill.
        fake_response = httpx.Response(200)
        self._verification(dict(notification), fake_response, reference)
        if notification.get("status") in ("VALID", "VALIDATED"):
            return text(notification.get("val_id", ""), "val_id", 50)
        return (
            None  # Failed/cancelled/pending IPN is a hint; query current server state.
        )

    def _refund_payload(self, request: RefundRequest) -> dict[str, str]:
        return dict(
            self._credentials(),
            bank_tran_id=request.bank_transaction_id,
            refund_trans_id=request.merchant_refund_id,
            refund_amount=amount(request.amount),
            refund_remarks=request.remarks,
        )

    def _refund(
        self,
        response: httpx.Response,
        bank_id: str,
        refund_id: str | None,
        request: RefundRequest | None = None,
    ) -> RefundResult:
        data = self._data(response)
        if data.get("APIConnect") != "DONE":
            raise unexpected(response, self.provider_name, data)
        if data.get("bank_tran_id") != bank_id:
            raise PaymentVerificationError(
                "SSLCommerz refund bank ID does not match",
                provider=self.provider_name,
                response_body=data,
            )
        status, provider_id = data.get("status"), data.get("refund_ref_id")
        if not isinstance(status, str) or not status:
            raise unexpected(response, self.provider_name, data)
        state = (
            {
                "success": RefundStatus.PENDING,
                "processing": RefundStatus.PENDING,
                "failed": RefundStatus.FAILED,
            }
            if request is not None
            else {"refunded": RefundStatus.REFUNDED, "processing": RefundStatus.PENDING}
        ).get(status, RefundStatus.UNKNOWN)
        # 'cancelled' has a contradictory description in the official table: unknown.
        if state in (RefundStatus.PENDING, RefundStatus.REFUNDED) and (
            not isinstance(provider_id, str) or not provider_id
        ):
            raise unexpected(response, self.provider_name, data)
        if refund_id is not None and provider_id != refund_id:
            raise PaymentVerificationError(
                "SSLCommerz refund reference does not match",
                provider=self.provider_name,
                response_body=data,
            )
        transaction = data.get("trans_id" if request is not None else "tran_id")
        if (
            request is not None
            and transaction != request.payment.merchant_transaction_id
        ):
            raise PaymentVerificationError(
                "SSLCommerz refund transaction does not match",
                provider=self.provider_name,
                response_body=data,
            )
        return RefundResult(
            bank_id,
            state,
            provider_id if isinstance(provider_id, str) else None,
            request.merchant_refund_id if request is not None else None,
            request.amount if request is not None else None,
            status,
            data,
            request.payment.currency if request is not None else None,
            transaction if isinstance(transaction, str) else None,
        )

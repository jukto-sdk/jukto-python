"""Durable SQLite entitlement example. Only apply results from SDK server verification.

No raw notifications are stored. Use one connection per operation; BEGIN IMMEDIATE
serializes budget/fulfillment changes across processes sharing a local database.
"""

from __future__ import annotations
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
import sqlite3
from typing import Iterator
from jukto import (
    BasePaymentProvider,
    PaymentReference,
    PaymentRequest,
    PaymentInitiationResult,
    PaymentVerificationResult,
    PaymentQueryResult,
    PaymentStatus,
    PaymentVerificationError,
    RefundRequest,
    RefundResult,
    RefundStatus,
)
from jukto.payments import amount


def cents(value: Decimal) -> int:
    return int(amount(value).replace(".", ""))


class PaymentLedger:
    def __init__(self, database: str | Path) -> None:
        self.database = str(database)
        if self.database == ":memory:":
            raise ValueError("This example requires a durable database path")
        with self._transaction() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS payments (
                    tran_id TEXT PRIMARY KEY, amount INTEGER NOT NULL, currency TEXT NOT NULL,
                    state TEXT NOT NULL, session_id TEXT, bank_id TEXT UNIQUE,
                    refund_hold INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS attempts (
                    bank_id TEXT PRIMARY KEY, val_id TEXT UNIQUE NOT NULL,
                    tran_id TEXT NOT NULL REFERENCES payments(tran_id));
                CREATE TABLE IF NOT EXISTS entitlements (
                    tran_id TEXT PRIMARY KEY REFERENCES payments(tran_id), bank_id TEXT UNIQUE NOT NULL);
                CREATE TABLE IF NOT EXISTS refunds (
                    refund_id TEXT PRIMARY KEY, tran_id TEXT NOT NULL REFERENCES payments(tran_id),
                    bank_id TEXT NOT NULL, amount INTEGER NOT NULL, remarks TEXT NOT NULL,
                    state TEXT NOT NULL, provider_id TEXT UNIQUE);
            """)

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.database, timeout=10)
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def create(self, reference: PaymentReference) -> None:
        # Duplicate references are rejected before dispatch; this is local deduplication.
        with self._transaction() as db:
            db.execute(
                "INSERT INTO payments(tran_id,amount,currency,state) VALUES(?,?,?,?)",
                (
                    reference.merchant_transaction_id,
                    cents(reference.amount),
                    reference.currency,
                    "reserved",
                ),
            )

    def expected(self, tran_id: str) -> PaymentReference:
        with self._transaction() as db:
            row = db.execute(
                "SELECT * FROM payments WHERE tran_id=?", (tran_id,)
            ).fetchone()
            if row is None:
                raise KeyError("Unknown application transaction")
            return PaymentReference(
                tran_id,
                Decimal(f"{row['amount'] // 100}.{row['amount'] % 100:02d}"),
                row["currency"],
            )

    def initiate(
        self, provider: BasePaymentProvider, request: PaymentRequest
    ) -> PaymentInitiationResult:
        self.create(request.reference)  # Commit before making an external call.
        try:
            result = provider.initiate(request)
        except BaseException:
            self._set_initial_state(
                request.reference.merchant_transaction_id, "unknown"
            )
            raise
        self._set_initial_state(
            request.reference.merchant_transaction_id,
            result.status.value,
            result.session_id,
        )
        return result

    def _set_initial_state(
        self, tran_id: str, state: str, session: str | None = None
    ) -> None:
        with self._transaction() as db:
            # IPN may verify and fulfill before initiation returns; never demote paid.
            db.execute(
                "UPDATE payments SET state=CASE WHEN state IN ('paid','review') THEN state ELSE ? END, "
                "session_id=COALESCE(?,session_id) WHERE tran_id=?",
                (state, session, tran_id),
            )

    def apply(self, result: PaymentVerificationResult) -> bool:
        reference = result.reference
        with self._transaction() as db:
            row = db.execute(
                "SELECT * FROM payments WHERE tran_id=?",
                (reference.merchant_transaction_id,),
            ).fetchone()
            if (
                row is None
                or row["amount"] != cents(reference.amount)
                or row["currency"] != reference.currency
            ):
                raise PaymentVerificationError(
                    "Verified result does not match durable order"
                )
            if result.status != PaymentStatus.PAID:
                if row["state"] not in ("paid", "review"):
                    db.execute(
                        "UPDATE payments SET state=? WHERE tran_id=?",
                        (result.status.value, reference.merchant_transaction_id),
                    )
                return False
            if not result.bank_transaction_id or not result.validation_id:
                raise PaymentVerificationError(
                    "Paid result lacks durable provider identifiers"
                )
            existing = db.execute(
                "SELECT * FROM attempts WHERE bank_id=? OR val_id=?",
                (result.bank_transaction_id, result.validation_id),
            ).fetchall()
            if any(
                item["tran_id"] != reference.merchant_transaction_id
                or item["bank_id"] != result.bank_transaction_id
                or item["val_id"] != result.validation_id
                for item in existing
            ):
                raise PaymentVerificationError(
                    "Provider payment identifiers are already bound to another attempt"
                )
            db.execute(
                "INSERT OR IGNORE INTO attempts(bank_id,val_id,tran_id) VALUES(?,?,?)",
                (
                    result.bank_transaction_id,
                    result.validation_id,
                    reference.merchant_transaction_id,
                ),
            )
            if not result.can_fulfill:
                if row["state"] != "paid":
                    db.execute(
                        "UPDATE payments SET state='review' WHERE tran_id=?",
                        (reference.merchant_transaction_id,),
                    )
                return False
            db.execute(
                "UPDATE payments SET state='paid', bank_id=COALESCE(bank_id,?) WHERE tran_id=?",
                (result.bank_transaction_id, reference.merchant_transaction_id),
            )
            # The entitlement itself is the durable business effect in this example.
            inserted = db.execute(
                "INSERT OR IGNORE INTO entitlements(tran_id,bank_id) VALUES(?,?)",
                (reference.merchant_transaction_id, result.bank_transaction_id),
            ).rowcount
            return inserted == 1

    def receive(
        self, provider: BasePaymentProvider, notification: dict[str, str], tran_id: str
    ) -> bool:
        expected = self.expected(
            tran_id
        )  # Application-selected order; never trust callback amount.
        result = provider.verify_notification(notification, expected)
        attempts = (
            result.attempts if isinstance(result, PaymentQueryResult) else (result,)
        )
        fulfilled = False
        for attempt in attempts:
            fulfilled = self.apply(attempt) or fulfilled
        return fulfilled

    def reserve_refund(
        self, tran_id: str, refund_id: str, value: Decimal, remarks: str
    ) -> RefundRequest:
        expected = self.expected(tran_id)
        with self._transaction() as db:
            row = db.execute(
                "SELECT * FROM payments WHERE tran_id=?", (tran_id,)
            ).fetchone()
            if (
                row is None
                or row["state"] != "paid"
                or not row["bank_id"]
                or row["refund_hold"]
            ):
                raise ValueError(
                    "Only fulfilled verified payments can be refunded in this example"
                )
            request = RefundRequest(expected, row["bank_id"], refund_id, value, remarks)
            reserved = db.execute(
                "SELECT COALESCE(SUM(amount),0) FROM refunds WHERE tran_id=? AND state!='failed'",
                (tran_id,),
            ).fetchone()[0]
            if reserved + cents(value) > row["amount"]:
                raise ValueError("Refund would exceed unreserved paid amount")
            db.execute(
                "INSERT INTO refunds(refund_id,tran_id,bank_id,amount,remarks,state) VALUES(?,?,?,?,?,?)",
                (refund_id, tran_id, row["bank_id"], cents(value), remarks, "reserved"),
            )
            return request

    def submit_refund(
        self, provider: BasePaymentProvider, request: RefundRequest
    ) -> RefundResult:
        # Claim once before dispatch: even concurrent callers cannot issue this GET twice.
        with self._transaction() as db:
            row = db.execute(
                "SELECT * FROM refunds WHERE refund_id=?", (request.merchant_refund_id,)
            ).fetchone()
            if (
                row is None
                or row["state"] != "reserved"
                or row["bank_id"] != request.bank_transaction_id
                or row["tran_id"] != request.payment.merchant_transaction_id
                or row["amount"] != cents(request.amount)
                or row["remarks"] != request.remarks
            ):
                raise ValueError(
                    "Refund must match an undispatched durable reservation"
                )
            db.execute(
                "UPDATE refunds SET state='unknown' WHERE refund_id=?",
                (request.merchant_refund_id,),
            )
        result = provider.refund(
            request
        )  # Exception/crash leaves unknown reservation in place.
        self.apply_refund(request.merchant_refund_id, result)
        return result

    def apply_refund(self, refund_id: str, result: RefundResult) -> None:
        contradictory = False
        with self._transaction() as db:
            row = db.execute(
                "SELECT * FROM refunds WHERE refund_id=?", (refund_id,)
            ).fetchone()
            if (
                row is None
                or row["bank_id"] != result.bank_transaction_id
                or (
                    result.merchant_refund_id is not None
                    and result.merchant_refund_id != refund_id
                )
                or (
                    result.requested_amount is not None
                    and cents(result.requested_amount) != row["amount"]
                )
            ):
                raise PaymentVerificationError(
                    "Refund result does not match durable reservation"
                )
            currency = db.execute(
                "SELECT currency FROM payments WHERE tran_id=?", (row["tran_id"],)
            ).fetchone()[0]
            if (result.currency is not None and result.currency != currency) or (
                result.merchant_transaction_id is not None
                and result.merchant_transaction_id != row["tran_id"]
            ):
                raise PaymentVerificationError(
                    "Refund currency or merchant transaction does not match reservation"
                )
            if (
                row["provider_id"] is not None
                and result.provider_refund_id != row["provider_id"]
            ):
                raise PaymentVerificationError("Refund provider ID changed")
            # Once refunded, stale pending/unknown/failed events cannot reopen the budget.
            state = "refunded" if row["state"] == "refunded" else result.status.value
            if result.status == RefundStatus.FAILED and row["provider_id"] is not None:
                state = row[
                    "state"
                ]  # A stale initiation failure cannot release a known refund.
            if row["state"] == "failed" and result.status != RefundStatus.FAILED:
                contradictory = True
                state = "unknown"
                db.execute(
                    "UPDATE payments SET refund_hold=1 WHERE tran_id=?",
                    (row["tran_id"],),
                )
            db.execute(
                "UPDATE refunds SET state=?, provider_id=COALESCE(provider_id,?) WHERE refund_id=?",
                (state, result.provider_refund_id, refund_id),
            )
        if contradictory:
            raise PaymentVerificationError(
                "Contradictory refund evidence requires manual reconciliation; further refunds held"
            )

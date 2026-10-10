"""Offline payment lifecycle regressions; official provenance is recorded separately."""

from decimal import Decimal
import httpx
import pytest
from jukto import (
    SSLCommerzClient,
    PaymentReference,
    PaymentRequest,
    PaymentCustomer,
    PaymentURLs,
    PaymentStatus,
)


def reference():
    return PaymentReference("synthetic-order", Decimal("100.00"), "BDT")


def request():
    return PaymentRequest(
        reference(),
        PaymentCustomer(
            "Synthetic",
            "synthetic@example.invalid",
            "01700000000",
            "Synthetic address",
            "Dhaka",
            "1000",
            "Bangladesh",
        ),
        PaymentURLs(
            "https://merchant.invalid/success",
            "https://merchant.invalid/fail",
            "https://merchant.invalid/cancel",
            "https://merchant.invalid/ipn",
        ),
        "Synthetic item",
        "Software",
    )


def test_hosted_checkout_is_customer_action_not_paid():
    seen = []

    def handler(req):
        seen.append(req)
        return httpx.Response(
            200,
            json={
                "status": "SUCCESS",
                "sessionkey": "synthetic-session",
                "GatewayPageURL": "https://sandbox.sslcommerz.com/checkout",
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as transport:
        with SSLCommerzClient(
            "synthetic-store", "synthetic-password", http_client=transport
        ) as provider:
            result = provider.initiate(request())
            assert result.status == PaymentStatus.REQUIRES_ACTION
            assert (
                result.reference == reference()
                and result.session_id == "synthetic-session"
            )
            assert b"total_amount=100.00" in seen[0].content
        assert not transport.is_closed


import asyncio
import hashlib
import json
from dataclasses import replace
from urllib.parse import parse_qs
from pathlib import Path
from contextlib import closing
import jukto
from jukto import (
    AsyncSSLCommerzClient,
    RefundRequest,
    RefundStatus,
    PaymentVerificationError,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def verified(status="VALID", **kwargs):
    return dict(
        {
            "status": status,
            "tran_id": "synthetic-order",
            "val_id": "synthetic-val",
            "bank_tran_id": "synthetic-bank",
            "amount": "100.00",
            "currency_amount": "100.00",
            "currency": "BDT",
            "currency_type": "BDT",
            "risk_level": "0",
        },
        **kwargs,
    )


def signed(status="VALID", **kwargs):
    data = dict(verified(status), store_id="synthetic-store")
    data.update(kwargs)
    keys = sorted(data)
    data["verify_key"] = ",".join(keys)
    values = dict(data, store_passwd=hashlib.md5(b"synthetic-password").hexdigest())
    canonical = "&".join(
        f"{key}={values[key]}" for key in sorted(keys + ["store_passwd"])
    )
    data["verify_sign"] = hashlib.md5(canonical.encode()).hexdigest()
    return data


def refund_request(value="25.00", refund_id="synthetic-refund"):
    return RefundRequest(
        reference(), "synthetic-bank", refund_id, Decimal(value), "Synthetic reason"
    )


def refund_body(status="success", **kwargs):
    return dict(
        {
            "APIConnect": "DONE",
            "bank_tran_id": "synthetic-bank",
            "trans_id": "synthetic-order",
            "tran_id": "synthetic-order",
            "refund_ref_id": "synthetic-ref",
            "status": status,
        },
        **kwargs,
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "operation",
    [
        "initiate",
        "verify",
        "query",
        "session",
        "refund",
        "refund_query",
        "notification",
    ],
)
async def test_sync_async_lifecycle_matches(operation):
    calls = []

    def handler(req):
        calls.append(
            (
                req.method,
                req.url.path,
                parse_qs(req.url.query.decode()),
                parse_qs(req.content.decode()),
            )
        )
        body = {
            "initiate": {
                "status": "SUCCESS",
                "sessionkey": "session",
                "GatewayPageURL": "https://sandbox.sslcommerz.com/checkout",
            },
            "verify": verified(),
            "query": {
                "APIConnect": "DONE",
                "no_of_trans_found": 1,
                "element": [verified()],
            },
            "session": dict(verified(), APIConnect="DONE", sessionkey="session"),
            "refund": refund_body(),
            "refund_query": refund_body("refunded"),
            "notification": verified(),
        }[operation]
        return httpx.Response(200, json=body)

    def call(client):
        return {
            "initiate": lambda: client.initiate(request()),
            "verify": lambda: client.verify("synthetic-val", reference()),
            "query": lambda: client.query_transaction(reference()),
            "session": lambda: client.query_session("session", reference()),
            "refund": lambda: client.refund(refund_request()),
            "refund_query": lambda: client.query_refund(
                "synthetic-ref", "synthetic-bank"
            ),
            "notification": lambda: client.verify_notification(signed(), reference()),
        }[operation]()

    with httpx.Client(transport=httpx.MockTransport(handler)) as transport:
        with SSLCommerzClient(
            "synthetic-store", "synthetic-password", http_client=transport
        ) as client:
            expected = call(client)
    expected_calls = calls[:]
    calls.clear()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        async with AsyncSSLCommerzClient(
            "synthetic-store", "synthetic-password", http_client=transport
        ) as client:
            assert await call(client) == expected
            assert (
                client.capabilities
                == SSLCommerzClient(
                    "synthetic-store", "synthetic-password"
                ).capabilities
            )
        assert not transport.is_closed
    assert calls == expected_calls
    if operation == "refund":
        assert calls[0][0] == "GET" and calls[0][2]["refund_trans_id"] == [
            "synthetic-refund"
        ]
        assert expected.status == RefundStatus.PENDING
    if operation == "verify":
        assert expected.can_fulfill


@pytest.mark.anyio
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize(
    "status",
    [
        "VALID",
        "VALIDATED",
        "PENDING",
        "FAILED",
        "CANCELLED",
        "EXPIRED",
        "UNATTEMPTED",
        "unpublished",
    ],
)
async def test_payment_states_conservative(asynchronous, status):
    cls, http_cls = (
        (AsyncSSLCommerzClient, httpx.AsyncClient)
        if asynchronous
        else (SSLCommerzClient, httpx.Client)
    )
    transport = http_cls(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json=verified(status))
        )
    )
    client = cls("synthetic-store", "synthetic-password", http_client=transport)
    result = client.verify("synthetic-val", reference())
    if asynchronous:
        result = await result
    assert result.status == {
        "VALID": PaymentStatus.PAID,
        "VALIDATED": PaymentStatus.PAID,
        "PENDING": PaymentStatus.PENDING,
        "FAILED": PaymentStatus.FAILED,
    }.get(status, PaymentStatus.UNKNOWN)
    assert result.can_fulfill == (status in ("VALID", "VALIDATED"))
    if asynchronous:
        await transport.aclose()
    else:
        transport.close()


@pytest.mark.parametrize(
    "change",
    [
        {"tran_id": "different"},
        {"val_id": "different"},
        {"amount": "99.00"},
        {"currency_amount": "99.00"},
        {"currency": "USD"},
        {"currency_type": "USD"},
        {"amount": "NaN"},
        {"store_id": "other-store"},
    ],
)
def test_verification_rejects_identity_amount_currency_mismatch(change):
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json=verified(**change))
        )
    ) as transport:
        client = SSLCommerzClient(
            "synthetic-store", "synthetic-password", http_client=transport
        )
        with pytest.raises(PaymentVerificationError):
            client.verify("synthetic-val", reference())


@pytest.mark.parametrize("risk", [None, "1", 1, "unknown", True, False])
def test_risk_missing_or_high_never_fulfills(risk):
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json=verified(risk_level=risk))
        )
    ) as transport:
        result = SSLCommerzClient(
            "synthetic-store", "synthetic-password", http_client=transport
        ).verify("synthetic-val", reference())
        assert (
            result.status == PaymentStatus.PAID
            and result.requires_review
            and not result.can_fulfill
        )


@pytest.mark.parametrize(
    "attack",
    [
        "signature",
        "amount",
        "store",
        "missing",
        "unsigned_val",
        "duplicate_keys",
        "password_key",
        "missing_signed_field",
        "list_value",
    ],
)
def test_spoofed_notification_fails_before_http(attack):
    data = signed()
    calls = []
    if attack == "signature":
        data["verify_sign"] = "0" * 32
    elif attack == "amount":
        data["amount"] = "1.00"
    elif attack == "store":
        data = signed(store_id="other")
    elif attack == "missing":
        del data["verify_sign"]
    elif attack == "unsigned_val":
        data["verify_key"] = (
            data["verify_key"].replace("val_id,", "").replace(",val_id", "")
        )
    elif attack == "duplicate_keys":
        data["verify_key"] += ",amount"
    elif attack == "password_key":
        data["verify_key"] += ",store_passwd"
        data["store_passwd"] = "opaque"
    elif attack == "missing_signed_field":
        del data["currency_amount"]
    else:
        data["amount"] = ["100.00", "1.00"]
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda r: calls.append(r) or httpx.Response(200, json=verified())
        )
    ) as transport:
        client = SSLCommerzClient(
            "synthetic-store", "synthetic-password", http_client=transport
        )
        with pytest.raises(PaymentVerificationError):
            client.verify_notification(data, reference())
    assert not calls


@pytest.mark.parametrize(
    "status", ["FAILED", "CANCELLED", "EXPIRED", "UNATTEMPTED", "PENDING"]
)
def test_non_success_notification_queries_current_state(status):
    requests = []

    def handler(req):
        requests.append(req)
        return httpx.Response(
            200,
            json={
                "APIConnect": "DONE",
                "no_of_trans_found": 2,
                "element": [verified("FAILED"), verified("VALIDATED")],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as transport:
        result = SSLCommerzClient(
            "synthetic-store", "synthetic-password", http_client=transport
        ).verify_notification(signed(status), reference())
    assert len(result.attempts) == 2 and result.attempts[1].can_fulfill
    assert requests[0].url.params["tran_id"] == "synthetic-order"


@pytest.mark.anyio
@pytest.mark.parametrize("operation", ["initiate", "refund", "verify"])
@pytest.mark.parametrize("failure", ["timeout", "connection", "500", "html", "302"])
async def test_ambiguous_side_effects_no_replay_both_interfaces(operation, failure):
    for asynchronous in (False, True):
        calls = []

        def handler(req):
            calls.append(req)
            if failure == "timeout":
                raise httpx.ReadTimeout("synthetic-password", request=req)
            if failure == "connection":
                raise httpx.ConnectError("synthetic-password", request=req)
            return httpx.Response(
                500 if failure == "500" else 302 if failure == "302" else 200,
                text="synthetic-password",
            )

        transport = (httpx.AsyncClient if asynchronous else httpx.Client)(
            transport=httpx.MockTransport(handler), follow_redirects=True
        )
        client = (AsyncSSLCommerzClient if asynchronous else SSLCommerzClient)(
            "synthetic-store", "synthetic-password", http_client=transport
        )
        with pytest.raises(jukto.ProviderError) as caught:
            result = (
                client.initiate(request())
                if operation == "initiate"
                else client.refund(refund_request())
                if operation == "refund"
                else client.verify("synthetic-val", reference())
            )
            if asynchronous:
                await result
        assert caught.value.reconciliation_required == (operation != "verify")
        assert caught.value.outcome == jukto.Outcome.UNKNOWN and len(calls) == 1
        assert "synthetic-password" not in str(caught.value)
        if asynchronous:
            await transport.aclose()
        else:
            transport.close()


@pytest.mark.parametrize(
    "operation", ["initiate", "verify", "query", "session", "refund", "refund_query"]
)
@pytest.mark.parametrize(
    "body", [None, [], {}, "opaque", {"status": "VALID"}, {"status": True}]
)
def test_malformed_payment_responses_are_normalized(operation, body):
    with httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body))
    ) as transport:
        client = SSLCommerzClient(
            "synthetic-store", "synthetic-password", http_client=transport
        )
        with pytest.raises(jukto.ProviderError):
            {
                "initiate": lambda: client.initiate(request()),
                "verify": lambda: client.verify("synthetic-val", reference()),
                "query": lambda: client.query_transaction(reference()),
                "session": lambda: client.query_session("session", reference()),
                "refund": lambda: client.refund(refund_request()),
                "refund_query": lambda: client.query_refund(
                    "synthetic-ref", "synthetic-bank"
                ),
            }[operation]()


@pytest.mark.parametrize(
    "value",
    [
        0,
        -1,
        10.1,
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("0.001"),
        Decimal("100000000"),
    ],
)
def test_exact_amount_inputs_rejected(value):
    with pytest.raises(jukto.JuktoValidationError):
        PaymentReference("synthetic", value, "BDT")


@pytest.mark.parametrize("currency", ["USD", "bdt", "", None])
def test_unsupported_currency_rejected(currency):
    with pytest.raises(jukto.JuktoValidationError):
        PaymentReference("synthetic", Decimal("100"), currency)


@pytest.mark.parametrize("mutation", ["customer", "email", "minimum", "maximum"])
def test_invalid_checkout_before_http(mutation):
    data = request()
    calls = []
    if mutation == "customer":
        data = replace(data, customer=replace(data.customer, name=""))
    elif mutation == "email":
        data = replace(data, customer=replace(data.customer, email="invalid"))
    else:
        data = replace(
            data,
            reference=PaymentReference(
                "synthetic",
                Decimal("9.99" if mutation == "minimum" else "500000.01"),
                "BDT",
            ),
        )
    with httpx.Client(
        transport=httpx.MockTransport(lambda r: calls.append(r))
    ) as transport:
        with pytest.raises(jukto.JuktoValidationError):
            SSLCommerzClient(
                "synthetic-store", "synthetic-password", http_client=transport
            ).initiate(data)
    assert not calls


@pytest.mark.parametrize(
    "url",
    ["http://merchant.invalid/ipn", "https://user:pass@merchant.invalid", "opaque"],
)
def test_insecure_callback_rejected(url):
    with pytest.raises(jukto.JuktoConfigurationError):
        PaymentURLs(url, url, url, url)


@pytest.mark.parametrize(
    "url",
    [
        "http://sandbox.sslcommerz.com/pay",
        "https://attacker.invalid/pay",
        "https://sandbox.sslcommerz.com:8443/pay",
        "opaque",
    ],
)
def test_untrusted_customer_action_url_rejected(url):
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200,
                json={"status": "SUCCESS", "sessionkey": "s", "GatewayPageURL": url},
            )
        )
    ) as transport:
        with pytest.raises(jukto.UnexpectedProviderResponseError):
            SSLCommerzClient(
                "synthetic-store", "synthetic-password", http_client=transport
            ).initiate(request())


@pytest.mark.parametrize(
    "status,expected",
    [
        ("success", RefundStatus.PENDING),
        ("processing", RefundStatus.PENDING),
        ("failed", RefundStatus.FAILED),
        ("opaque", RefundStatus.UNKNOWN),
    ],
)
def test_refund_initiation_states(status, expected):
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json=refund_body(status))
        )
    ) as transport:
        result = SSLCommerzClient(
            "synthetic-store", "synthetic-password", http_client=transport
        ).refund(refund_request())
        assert result.status == expected and result.requested_amount == Decimal("25.00")


@pytest.mark.parametrize(
    "status,expected",
    [
        ("refunded", RefundStatus.REFUNDED),
        ("processing", RefundStatus.PENDING),
        ("cancelled", RefundStatus.UNKNOWN),
        ("opaque", RefundStatus.UNKNOWN),
    ],
)
def test_refund_query_states(status, expected):
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json=refund_body(status))
        )
    ) as transport:
        assert (
            SSLCommerzClient(
                "synthetic-store", "synthetic-password", http_client=transport
            )
            .query_refund("synthetic-ref", "synthetic-bank")
            .status
            == expected
        )


def test_float_risk_does_not_certify_safe_transaction():
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json=verified(risk_level=0.0))
        )
    ) as transport:
        result = SSLCommerzClient(
            "synthetic-store", "synthetic-password", http_client=transport
        ).verify("synthetic-val", reference())
        assert not result.can_fulfill


def test_ledger_risky_paid_and_stale_failure_remain_on_hold(tmp_path):
    from examples.payment_ledger import PaymentLedger

    ledger = PaymentLedger(tmp_path / "payments.sqlite")
    ledger.create(reference())
    risky = jukto.PaymentVerificationResult(
        reference(), PaymentStatus.PAID, "v", "b", True
    )
    assert not ledger.apply(risky)
    ledger.apply(jukto.PaymentVerificationResult(reference(), PaymentStatus.FAILED))
    import sqlite3

    with closing(sqlite3.connect(tmp_path / "payments.sqlite")) as db:
        assert db.execute("SELECT state FROM payments").fetchone()[0] == "review"


def test_ledger_pending_refund_cannot_be_reopened_by_stale_failed_result(tmp_path):
    from examples.payment_ledger import PaymentLedger

    ledger = PaymentLedger(tmp_path / "payments.sqlite")
    ledger.create(reference())
    ledger.apply(
        jukto.PaymentVerificationResult(
            reference(), PaymentStatus.PAID, "v", "synthetic-bank", False
        )
    )
    request = ledger.reserve_refund("synthetic-order", "r", Decimal("100"), "Synthetic")
    pending = jukto.RefundResult(
        "synthetic-bank", RefundStatus.PENDING, "p", "r", Decimal("100")
    )
    ledger.apply_refund("r", pending)
    ledger.apply_refund("r", replace(pending, status=RefundStatus.FAILED))
    with pytest.raises(ValueError):
        ledger.reserve_refund("synthetic-order", "r2", Decimal("1"), "Synthetic")


def test_sdk_payment_httpx_logs_do_not_expose_query_credentials(caplog):
    import logging

    caplog.set_level(logging.INFO, logger="httpx")
    with httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=verified()))
    ) as transport:
        SSLCommerzClient(
            "synthetic-store", "synthetic-password", http_client=transport
        ).verify("synthetic-val", reference())
    assert "synthetic-password" not in caplog.text
    assert "synthetic-val" not in caplog.text


@pytest.mark.parametrize(
    "status,exception",
    [
        ("FAILED", jukto.ProviderAuthenticationError),
        ("INACTIVE", jukto.ProviderAuthenticationError),
        ("INVALID_REQUEST", jukto.InvalidRequestError),
        ("opaque", jukto.UnexpectedProviderResponseError),
    ],
)
def test_documented_api_connection_errors(status, exception):
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json={"APIConnect": status})
        )
    ) as transport:
        with pytest.raises(exception):
            SSLCommerzClient(
                "synthetic-store", "synthetic-password", http_client=transport
            ).query_transaction(reference())


@pytest.mark.parametrize("status", [400, 401, 403, 422, 429, 500, 302])
def test_http_error_metadata(status):
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                status, headers={"X-Request-ID": "safe-id", "Retry-After": "5"}
            )
        )
    ) as transport:
        with pytest.raises(jukto.ProviderError) as caught:
            SSLCommerzClient(
                "synthetic-store", "synthetic-password", http_client=transport
            ).verify("synthetic-val", reference())
        assert (
            caught.value.http_status == status
            and caught.value.request_id == "safe-id"
            and caught.value.retry_after == "5"
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "invalid_id",
        "empty_status",
        "missing_val",
        "missing_bank",
        "float_amount",
        "bool_amount",
        "malformed_decimal",
    ],
)
def test_verification_schema_guards(mutation):
    body = verified()
    if mutation == "invalid_id":
        body["status"] = "INVALID_TRANSACTION"
    elif mutation == "empty_status":
        body["status"] = ""
    elif mutation == "missing_val":
        del body["val_id"]
    elif mutation == "missing_bank":
        body["bank_tran_id"] = ""
    else:
        body["amount"] = {
            "float_amount": 100.0,
            "bool_amount": True,
            "malformed_decimal": "bad",
        }[mutation]
    with httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body))
    ) as transport:
        with pytest.raises(jukto.ProviderError):
            SSLCommerzClient(
                "synthetic-store", "synthetic-password", http_client=transport
            ).verify("synthetic-val", reference())


@pytest.mark.parametrize(
    "body",
    [
        {"status": "FAILED"},
        {"status": "unpublished"},
        {"status": "SUCCESS"},
        {
            "status": "SUCCESS",
            "sessionkey": False,
            "GatewayPageURL": "https://sandbox.sslcommerz.com/checkout",
        },
    ],
)
def test_initiation_error_or_schema(body):
    with httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body))
    ) as transport:
        client = SSLCommerzClient(
            "synthetic-store", "synthetic-password", http_client=transport
        )
        if body["status"] == "FAILED":
            assert client.initiate(request()).status == PaymentStatus.FAILED
        else:
            with pytest.raises(jukto.UnexpectedProviderResponseError):
                client.initiate(request())


@pytest.mark.parametrize(
    "body",
    [
        {"APIConnect": "DONE", "no_of_trans_found": 0, "element": []},
        {"APIConnect": "DONE", "no_of_trans_found": 1, "element": []},
        {"APIConnect": "DONE", "no_of_trans_found": 1, "element": ["bad"]},
        {"APIConnect": "DONE", "no_of_trans_found": True, "element": []},
    ],
)
def test_query_counts_and_empty_unknown(body):
    with httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body))
    ) as transport:
        client = SSLCommerzClient(
            "synthetic-store", "synthetic-password", http_client=transport
        )
        if body["no_of_trans_found"] == 0:
            assert client.query_transaction(reference()).attempts == ()
        else:
            with pytest.raises(jukto.UnexpectedProviderResponseError):
                client.query_transaction(reference())


@pytest.mark.parametrize(
    "body",
    [
        dict(verified(), APIConnect="DONE", sessionkey="other"),
        dict(verified(), sessionkey="session"),
    ],
)
def test_session_query_rejects_missing_or_wrong_identity(body):
    with httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body))
    ) as transport:
        with pytest.raises(jukto.UnexpectedProviderResponseError):
            SSLCommerzClient(
                "synthetic-store", "synthetic-password", http_client=transport
            ).query_session("session", reference())


@pytest.mark.parametrize(
    "change",
    [
        {"bank_tran_id": "other"},
        {"trans_id": "other"},
        {"refund_ref_id": ""},
        {"status": False},
        {"APIConnect": None},
    ],
)
def test_refund_malformed_or_wrong_identity(change):
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json=refund_body(**change))
        )
    ) as transport:
        with pytest.raises(jukto.ProviderError):
            SSLCommerzClient(
                "synthetic-store", "synthetic-password", http_client=transport
            ).refund(refund_request())


def test_refund_query_wrong_reference():
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200, json=refund_body("refunded", refund_ref_id="other")
            )
        )
    ) as transport:
        with pytest.raises(PaymentVerificationError):
            SSLCommerzClient(
                "synthetic-store", "synthetic-password", http_client=transport
            ).query_refund("synthetic-ref", "synthetic-bank")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"store_id": ""},
        {"store_password": ""},
        {"store_id": "x" * 31},
        {"sandbox": "false"},
    ],
)
def test_invalid_credentials_or_environment(kwargs):
    args = dict(store_id="synthetic-store", store_password="synthetic-password")
    args.update(kwargs)
    with pytest.raises(jukto.JuktoConfigurationError):
        SSLCommerzClient(**args)


def test_refund_bounds_and_text_inputs():
    with pytest.raises(jukto.JuktoValidationError):
        refund_request("100.01")
    with pytest.raises(jukto.JuktoValidationError):
        refund_request(refund_id="")
    with pytest.raises(jukto.JuktoValidationError):
        PaymentReference("", Decimal("100"), "BDT")
    with pytest.raises(jukto.JuktoValidationError):
        PaymentURLs("", "", "", "")


def test_money_serialization_is_independent_of_decimal_context():
    from decimal import localcontext
    from jukto.payments import amount

    with localcontext() as context:
        context.prec = 2
        assert amount(Decimal("123456.78")) == "123456.78"


@pytest.mark.anyio
async def test_owned_payment_pool_cancellation_and_log_scope(monkeypatch, caplog):
    import logging

    gate = asyncio.Event()
    instances = []
    original = httpx.AsyncClient

    async def handler(req):
        gate.set()
        await asyncio.Event().wait()

    class Owned(original):
        def __init__(self, **kwargs):
            super().__init__(transport=httpx.MockTransport(handler), **kwargs)
            instances.append(self)

    monkeypatch.setattr(httpx, "AsyncClient", Owned)
    provider = AsyncSSLCommerzClient("synthetic-store", "synthetic-password")

    async def run():
        async with provider:
            await provider.refund(refund_request())

    task = asyncio.create_task(run())
    await asyncio.wait_for(gate.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert instances[0].is_closed
    caplog.set_level(logging.INFO, logger="httpx")
    logging.getLogger("httpx").info("outside SDK remains visible")
    assert "outside SDK remains visible" in caplog.text


def test_durable_duplicate_and_reordered_events(tmp_path):
    from examples.payment_ledger import PaymentLedger

    path = tmp_path / "payments.sqlite"
    ledger = PaymentLedger(path)
    ledger.create(reference())
    paid = jukto.PaymentVerificationResult(
        reference(), PaymentStatus.PAID, "v", "b", False
    )
    assert ledger.apply(paid)
    assert not PaymentLedger(path).apply(paid)  # Restart persists deduplication.
    assert not ledger.apply(replace(paid, status=PaymentStatus.PENDING))
    assert not ledger.apply(replace(paid, status=PaymentStatus.FAILED))
    assert not ledger.apply(replace(paid, validation_id="v2", bank_transaction_id="b2"))
    import sqlite3

    with closing(sqlite3.connect(path)) as db:
        assert db.execute("SELECT COUNT(*) FROM entitlements").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0] == 2
        assert db.execute("SELECT state FROM payments").fetchone()[0] == "paid"


def test_concurrent_duplicate_fulfillment_is_transactional(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from examples.payment_ledger import PaymentLedger

    ledger = PaymentLedger(tmp_path / "payments.sqlite")
    ledger.create(reference())
    paid = jukto.PaymentVerificationResult(
        reference(), PaymentStatus.PAID, "v", "b", False
    )
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(lambda _: ledger.apply(paid), range(16))) == 1


def test_application_ledger_matches_stored_order_and_provider_ids(tmp_path):
    from examples.payment_ledger import PaymentLedger

    ledger = PaymentLedger(tmp_path / "payments.sqlite")
    ledger.create(reference())
    paid = jukto.PaymentVerificationResult(
        reference(), PaymentStatus.PAID, "v", "b", False
    )
    ledger.apply(paid)
    with pytest.raises(PaymentVerificationError):
        ledger.apply(
            replace(
                paid,
                reference=PaymentReference("synthetic-order", Decimal("99"), "BDT"),
            )
        )
    second = PaymentReference("second", Decimal("100"), "BDT")
    ledger.create(second)
    with pytest.raises(PaymentVerificationError):
        ledger.apply(replace(paid, reference=second))
    with pytest.raises(PaymentVerificationError):
        ledger.apply(replace(paid, validation_id=None))


def test_durable_initiation_timeout_and_no_redispatch(tmp_path):
    from examples.payment_ledger import PaymentLedger
    import sqlite3

    calls = []

    def handler(req):
        calls.append(req)
        raise httpx.ReadTimeout("opaque", request=req)

    ledger = PaymentLedger(tmp_path / "payments.sqlite")
    with httpx.Client(transport=httpx.MockTransport(handler)) as transport:
        client = SSLCommerzClient(
            "synthetic-store", "synthetic-password", http_client=transport
        )
        with pytest.raises(jukto.ProviderTimeoutError):
            ledger.initiate(client, request())
        with pytest.raises(sqlite3.IntegrityError):
            ledger.initiate(client, request())
    assert len(calls) == 1
    with closing(sqlite3.connect(ledger.database)) as db:
        assert db.execute("SELECT state FROM payments").fetchone()[0] == "unknown"


def test_partial_refund_reservations_timeout_and_monotonic_query(tmp_path):
    from examples.payment_ledger import PaymentLedger

    ledger = PaymentLedger(tmp_path / "payments.sqlite")
    ledger.create(reference())
    ledger.apply(
        jukto.PaymentVerificationResult(
            reference(), PaymentStatus.PAID, "v", "synthetic-bank", False
        )
    )
    first = ledger.reserve_refund("synthetic-order", "r1", Decimal("25"), "Synthetic")

    def timeout(req):
        raise httpx.ReadTimeout("opaque", request=req)

    with httpx.Client(transport=httpx.MockTransport(timeout)) as transport:
        provider = SSLCommerzClient(
            "synthetic-store", "synthetic-password", http_client=transport
        )
        with pytest.raises(jukto.ProviderTimeoutError):
            ledger.submit_refund(provider, first)
        with pytest.raises(ValueError):
            ledger.submit_refund(provider, first)
    second = ledger.reserve_refund("synthetic-order", "r2", Decimal("75"), "Synthetic")
    with pytest.raises(ValueError):
        ledger.reserve_refund("synthetic-order", "r3", Decimal("0.01"), "Synthetic")
    pending = jukto.RefundResult(
        "synthetic-bank", RefundStatus.PENDING, "p2", "r2", Decimal("75")
    )
    ledger.apply_refund("r2", pending)
    ledger.apply_refund(
        "r2",
        replace(
            pending,
            status=RefundStatus.REFUNDED,
            merchant_refund_id=None,
            requested_amount=None,
        ),
    )
    ledger.apply_refund("r2", pending)
    with pytest.raises(ValueError):
        ledger.reserve_refund("synthetic-order", "r3", Decimal("0.01"), "Synthetic")


def test_failed_refund_releases_only_unaccepted_reservation(tmp_path):
    from examples.payment_ledger import PaymentLedger

    ledger = PaymentLedger(tmp_path / "payments.sqlite")
    ledger.create(reference())
    ledger.apply(
        jukto.PaymentVerificationResult(
            reference(), PaymentStatus.PAID, "v", "synthetic-bank", False
        )
    )
    ledger.reserve_refund("synthetic-order", "r1", Decimal("100"), "Synthetic")
    ledger.apply_refund(
        "r1",
        jukto.RefundResult(
            "synthetic-bank", RefundStatus.FAILED, None, "r1", Decimal("100")
        ),
    )
    assert ledger.reserve_refund(
        "synthetic-order", "r2", Decimal("100"), "Synthetic"
    ).amount == Decimal("100")


def test_review_attempt_cannot_become_wrong_refund_bank(tmp_path):
    from examples.payment_ledger import PaymentLedger

    ledger = PaymentLedger(tmp_path / "payments.sqlite")
    ledger.create(reference())
    ledger.apply(
        jukto.PaymentVerificationResult(
            reference(), PaymentStatus.PAID, "risk-val", "risk-bank", True
        )
    )
    assert ledger.apply(
        jukto.PaymentVerificationResult(
            reference(), PaymentStatus.PAID, "safe-val", "safe-bank", False
        )
    )
    assert (
        ledger.reserve_refund(
            "synthetic-order", "r", Decimal("10"), "Synthetic"
        ).bank_transaction_id
        == "safe-bank"
    )


def test_sqlite_begin_failure_closes_connection(monkeypatch, tmp_path):
    from examples.payment_ledger import PaymentLedger
    import sqlite3

    ledger = PaymentLedger(tmp_path / "payments.sqlite")
    closed = []

    class Failing:
        def execute(self, statement):
            if statement == "BEGIN IMMEDIATE":
                raise sqlite3.OperationalError("locked")

        def rollback(self):
            pass

        def close(self):
            closed.append(True)

    monkeypatch.setattr(sqlite3, "connect", lambda *a, **k: Failing())
    with pytest.raises(sqlite3.OperationalError):
        ledger.expected("synthetic-order")
    assert closed == [True]


def test_contradictory_refund_after_definitive_failure_holds_future_refunds(tmp_path):
    from examples.payment_ledger import PaymentLedger

    ledger = PaymentLedger(tmp_path / "payments.sqlite")
    ledger.create(reference())
    ledger.apply(
        jukto.PaymentVerificationResult(
            reference(), PaymentStatus.PAID, "v", "synthetic-bank", False
        )
    )
    ledger.reserve_refund("synthetic-order", "r1", Decimal("50"), "Synthetic")
    ledger.apply_refund(
        "r1",
        jukto.RefundResult(
            "synthetic-bank", RefundStatus.FAILED, None, "r1", Decimal("50")
        ),
    )
    with pytest.raises(PaymentVerificationError):
        ledger.apply_refund(
            "r1",
            jukto.RefundResult(
                "synthetic-bank", RefundStatus.PENDING, "p1", "r1", Decimal("50")
            ),
        )
    with pytest.raises(ValueError):
        ledger.reserve_refund("synthetic-order", "r2", Decimal("1"), "Synthetic")


def test_complete_offline_hosted_payment_and_partial_refund_lifecycle(tmp_path):
    from examples.payment_ledger import PaymentLedger

    calls = []
    refunded = False

    def handler(req):
        calls.append(req)
        if req.method == "POST":
            return httpx.Response(
                200,
                json={
                    "status": "SUCCESS",
                    "sessionkey": "session",
                    "GatewayPageURL": "https://sandbox.sslcommerz.com/checkout",
                },
            )
        params = req.url.params
        if "val_id" in params:
            return httpx.Response(200, json=verified("VALIDATED"))
        if "refund_amount" in params:
            return httpx.Response(
                200,
                json=refund_body(refund_ref_id="provider-" + params["refund_trans_id"]),
            )
        if "refund_ref_id" in params:
            return httpx.Response(
                200,
                json=refund_body(
                    "refunded" if refunded else "processing",
                    refund_ref_id=params["refund_ref_id"],
                ),
            )
        return httpx.Response(
            200,
            json={
                "APIConnect": "DONE",
                "no_of_trans_found": 2,
                "element": [verified("FAILED"), verified("VALIDATED")],
            },
        )

    ledger = PaymentLedger(tmp_path / "payments.sqlite")
    with httpx.Client(transport=httpx.MockTransport(handler)) as transport:
        provider = SSLCommerzClient(
            "synthetic-store", "synthetic-password", http_client=transport
        )
        assert (
            ledger.initiate(provider, request()).status == PaymentStatus.REQUIRES_ACTION
        )
        assert ledger.receive(provider, signed(), "synthetic-order")
        assert not ledger.receive(provider, signed(), "synthetic-order")
        assert not ledger.receive(provider, signed("FAILED"), "synthetic-order")
        refund = ledger.reserve_refund(
            "synthetic-order", "r1", Decimal("25"), "Synthetic"
        )
        assert ledger.submit_refund(provider, refund).status == RefundStatus.PENDING
        pending = provider.query_refund("provider-r1", "synthetic-bank")
        ledger.apply_refund("r1", pending)
        refunded = True
        ledger.apply_refund(
            "r1", provider.query_refund("provider-r1", "synthetic-bank")
        )
        ledger.apply_refund("r1", pending)  # Late processing cannot undo refunded.
        assert ledger.reserve_refund(
            "synthetic-order", "r2", Decimal("75"), "Synthetic"
        ).amount == Decimal("75")
        assert len(calls) == 7


def test_concurrent_refund_budget_cannot_over_reserve(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from examples.payment_ledger import PaymentLedger

    ledger = PaymentLedger(tmp_path / "payments.sqlite")
    ledger.create(reference())
    ledger.apply(
        jukto.PaymentVerificationResult(
            reference(), PaymentStatus.PAID, "v", "synthetic-bank", False
        )
    )

    def reserve(index):
        try:
            ledger.reserve_refund(
                "synthetic-order", str(index), Decimal("20"), "Synthetic"
            )
            return True
        except ValueError:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(reserve, range(10))) == 5


def test_ledger_unknown_order_refund_mismatch_and_no_memory_db(tmp_path):
    from examples.payment_ledger import PaymentLedger

    with pytest.raises(ValueError):
        PaymentLedger(":memory:")
    ledger = PaymentLedger(tmp_path / "payments.sqlite")
    ledger.create(reference())
    with pytest.raises(KeyError):
        ledger.expected("other")
    with pytest.raises(ValueError):
        ledger.reserve_refund("synthetic-order", "r", Decimal("1"), "Synthetic")
    ledger.apply(
        jukto.PaymentVerificationResult(
            reference(), PaymentStatus.PAID, "v", "synthetic-bank", False
        )
    )
    ledger.reserve_refund("synthetic-order", "r", Decimal("25"), "Synthetic")
    pending = jukto.RefundResult(
        "synthetic-bank", RefundStatus.PENDING, "p", "r", Decimal("25")
    )
    for mutation in (
        replace(pending, bank_transaction_id="other"),
        replace(pending, merchant_refund_id="other"),
        replace(pending, requested_amount=Decimal("24")),
    ):
        with pytest.raises(PaymentVerificationError):
            ledger.apply_refund("r", mutation)
    ledger.apply_refund("r", pending)
    with pytest.raises(PaymentVerificationError):
        ledger.apply_refund("r", replace(pending, provider_refund_id="other"))


@pytest.mark.anyio
async def test_async_non_success_notification_query_and_safe_httpx_log(caplog):
    import logging

    caplog.set_level(logging.INFO, logger="httpx")
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200,
                json={
                    "APIConnect": "DONE",
                    "no_of_trans_found": 1,
                    "element": [verified()],
                },
            )
        )
    ) as transport:
        async with AsyncSSLCommerzClient(
            "synthetic-store", "synthetic-password", http_client=transport
        ) as provider:
            assert (
                (await provider.verify_notification(signed("CANCELLED"), reference()))
                .attempts[0]
                .can_fulfill
            )
    assert (
        "synthetic-password" not in caplog.text and "synthetic-order" not in caplog.text
    )


def test_initiation_reply_cannot_demote_prior_verified_payment(tmp_path):
    from examples.payment_ledger import PaymentLedger

    ledger = PaymentLedger(tmp_path / "payments.sqlite")

    def handler(req):
        ledger.apply(
            jukto.PaymentVerificationResult(
                reference(), PaymentStatus.PAID, "v", "synthetic-bank", False
            )
        )
        return httpx.Response(
            200,
            json={
                "status": "SUCCESS",
                "sessionkey": "session",
                "GatewayPageURL": "https://sandbox.sslcommerz.com/checkout",
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as transport:
        ledger.initiate(
            SSLCommerzClient(
                "synthetic-store", "synthetic-password", http_client=transport
            ),
            request(),
        )
    assert ledger.reserve_refund(
        "synthetic-order", "r", Decimal("25"), "Synthetic"
    ).amount == Decimal("25")


def test_reuse_owned_sync_pool_and_production_host_without_network(monkeypatch):
    original = httpx.Client
    instances = []

    class Owned(original):
        def __init__(self, **kwargs):
            assert kwargs["verify"] is True and kwargs["follow_redirects"] is False
            super().__init__(
                transport=httpx.MockTransport(
                    lambda r: httpx.Response(200, json=verified())
                ),
                **kwargs,
            )
            instances.append(self)

    monkeypatch.setattr(httpx, "Client", Owned)
    provider = SSLCommerzClient("synthetic-store", "synthetic-password", sandbox=False)
    with provider:
        assert provider.base_url == "https://securepay.sslcommerz.com"
        provider.verify("synthetic-val", reference())
        provider.verify("synthetic-val", reference())
    assert len(instances) == 1 and instances[0].is_closed
    with pytest.raises(jukto.JuktoConfigurationError):
        provider.verify("synthetic-val", reference())


@pytest.mark.parametrize(
    "body",
    [b"amount=100&amount=1", b"invalid", b"amount=%FF", b"x=" * 40000, "not-bytes"],
)
def test_notification_form_boundary_rejects_ambiguous_input(body):
    with pytest.raises(PaymentVerificationError):
        SSLCommerzClient.parse_notification(body)


def test_notification_form_and_literal_unicode_hash_values():
    from urllib.parse import urlencode

    data = signed(value_a="বাংলা & = synthetic")
    assert SSLCommerzClient.parse_notification(urlencode(data).encode()) == data
    with httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=verified()))
    ) as transport:
        assert (
            SSLCommerzClient(
                "synthetic-store", "synthetic-password", http_client=transport
            )
            .verify_notification(data, reference())
            .can_fulfill
        )


CONTRACT = json.loads(
    (Path(__file__).parent / "fixtures/sslcommerz_contract.json").read_text()
)


@pytest.mark.parametrize("status,expected", CONTRACT["query_states"])
def test_recorded_official_payment_status_contract(status, expected):
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json=verified(status))
        )
    ) as transport:
        assert (
            SSLCommerzClient(
                "synthetic-store", "synthetic-password", http_client=transport
            )
            .verify("synthetic-val", reference())
            .status.value
            == expected
        )


def test_recorded_signature_vector_and_provenance():
    vector = CONTRACT["synthetic_signature_vector"]
    calls = []
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda r: calls.append(r) or httpx.Response(200, json=verified())
        )
    ) as transport:
        client = SSLCommerzClient(
            vector["store_id"], vector["store_password"], http_client=transport
        )
        assert client.verify_notification(
            vector["notification"], reference()
        ).can_fulfill
    assert len(calls) == 1
    assert CONTRACT["refund_trans_id"] == {
        "mandatory": True,
        "introduced": "2025-02-24",
    }
    assert "/blob/" in CONTRACT["provenance"]["official_signature_implementation"]


def test_invalid_fractional_money_is_normalized_with_decimal_traps_enabled():
    from decimal import localcontext, Inexact

    with localcontext() as context:
        context.traps[Inexact] = True
        with pytest.raises(jukto.JuktoValidationError):
            PaymentReference("synthetic", Decimal("0.001"), "BDT")

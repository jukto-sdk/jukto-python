---
title: "Experimental SSLCOMMERZ Python Payment Integration"
description: "Explore Jukto experimental SSLCOMMERZ hosted BDT payments, server verification and refunds. Merchant lifecycle verification remains pending."
---

# Hosted payments (experimental alpha)

The 0.1.0a1 alpha includes `SSLCommerzClient` and `AsyncSSLCommerzClient` for one
experimental hosted checkout integration. The alpha is available on [PyPI](https://pypi.org/project/jukto/0.1.0a1/). Read the
[contract audit](../payment-contracts.md) before using it: BDT, non-physical goods,
no shipping/EMI, and no live/sandbox transaction certification. Standalone bKash
and Nagad remain planned.

```python
from decimal import Decimal
from jukto import SSLCommerzClient, PaymentReference, PaymentRequest, PaymentCustomer, PaymentURLs

reference = PaymentReference("synthetic-order", Decimal("100.00"), "BDT")
request = PaymentRequest(
    reference,
    PaymentCustomer("Synthetic", "synthetic@example.invalid", "01700000000",
                    "Synthetic address", "Dhaka", "1000", "Bangladesh"),
    PaymentURLs("https://merchant.invalid/success", "https://merchant.invalid/fail",
                "https://merchant.invalid/cancel", "https://merchant.invalid/ipn"),
    "Synthetic item", "Software",
)
```

This creates models only. Inject synthetic `httpx.MockTransport` responses to test
operations; real credentials cause real HTTP. Constructors are lazy. Use `with`
and `close()` for sync clients or `async with`/`aclose()` for native asyncio clients;
borrowed `httpx.Client`/`AsyncClient` pools remain owner-managed. Async methods use
`await` and the same typed models, parsers and policies. Finish in-flight requests
before shutdown, as described in the [async guide](async.md).

`initiate(request)` returns a session and customer-action URL, not paid status.
Persist the application reference before dispatch and the session before redirect.
On return/IPN, call `verify(validation_id, stored_reference)` or
`verify_notification(single_value_form, stored_reference)`. Always obtain expected
amount/currency/transaction from your database. `parse_notification(body_bytes)`
rejects duplicate fields; an HTTP adapter must also require the form content type,
apply ingress limits and avoid logging the body. `verify_notification` verifies
signed fields and performs the server lookup; it cannot be used offline as a mere
signature badge. A signed negative notification triggers a transaction query.

Only a server-verified result with `can_fulfill=True` can grant fulfillment.
`query_transaction(stored_reference)` returns every attempt; multiple paid attempts
may be duplicate charges needing review/refund, not multiple entitlements.
`query_session(session_id, stored_reference)` requires the returned session to match.
Unknown statuses and high/missing risk levels never grant fulfillment.

`refund(RefundRequest(...))` sends the documented state-changing GET once.
`success` means initiation, not returned funds. Save its provider refund reference,
then use `query_refund(provider_refund_id, expected_bank_transaction_id)`.
Reserve partial refund amounts transactionally before dispatch. A timeout or
cancellation can leave an upstream effect; retain reservations and reconcile before
retrying. Neither merchant IDs nor a failed browser callback provide idempotency.
The stateless SDK cannot enforce a cumulative refund budget across workers.

## Durable application example

The example stores references, session state, verified payment attempts, digital
entitlements and refund reservations in a local SQLite file. An entitlement row is
the business effect; insertion and payment update share a transaction and unique
constraints. It survives restart and concurrent duplicate notifications. Stale
negative events cannot demote paid/reviewed payments; additional paid attempts are
recorded without granting another entitlement. Reviewed-risk attempts are not used
as the refund bank for a later safe payment. Refund budgets include unknown,
pending and already refunded amounts. Contradictory refund evidence holds further
refunds for manual reconciliation.

```python
--8<-- "examples/payment_ledger.py"
```

Use a new database for this example; it is not a production schema migration tool.
Call `ledger.initiate(provider, request)` before redirect; call
`ledger.receive(provider, decoded_form, application_selected_tran_id)` from a sync
request/worker. The network lookup happens outside database write transactions;
only verified results are applied. Never construct a paid result from callback data.
Use `reserve_refund` then `submit_refund` once, and `apply_refund` for subsequent
verified queries. An uncertain dispatch blocks local replay; recovery queries the
stored session/merchant reference or uses manual reconciliation when a refund ID
was never received. The example has no HTTP endpoint, authentication, background
reconciler, migrations or operator tools. SQLite calls block; async servers need a
worker or an appropriate async database implementation.

A database entitlement transaction does not make external shipment/email delivery
exactly once. For external fulfillment, store an outbox in the same transaction
and give consumers durable deduplication. Separate business order IDs from payment
attempt IDs in a production schema; the example treats its transaction ID as the
entitlement's identity. No SDK can infer your business's deduplication boundary.

## Sensitive diagnostics

Provider raw responses and request models can contain personal/financial data.
SSLCOMMERZ's documented GET APIs put credentials in URL query parameters. During
SDK payment requests, a context-local filter replaces HTTPX logger records with
fixed metadata, including on borrowed clients. Other HTTPX traffic is unchanged.
Application event hooks, proxy/APM access logs, custom transports and application
logs still need their own URL/body sanitization. Never log raw callbacks, checkout
URLs, credentials or exception response bodies.

```bash
python -m pytest tests/test_payments.py --no-cov
```

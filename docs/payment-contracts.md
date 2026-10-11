---
title: "SSLCOMMERZ hosted payment contract audit"
description: "Review SSLCOMMERZ hosted checkout, verification and refund contracts, scoped BDT support and unresolved merchant lifecycle evidence."
---

# SSLCOMMERZ hosted payment contract audit

Checked **2026-10-10** against the [official v4 specification](https://developer.sslcommerz.com/doc/v4/),
its [signature specification](https://developer.sslcommerz.com/docs.html), and the
[official PHP signature implementation at an immutable commit](https://github.com/sslcommerz/SSLCommerz-PHP/blob/46fdf3a68ab8f071d38c334078065bbd45d3fcfc/lib/SslCommerzNotification.php#L163).
Version 4.00 is displayed with a May 2019 date, but the refund section contains a
February 2025 change. These are published contracts, not observed provider traffic.
`tests/fixtures/sslcommerz_contract.json` records provenance and derived SDK policies;
its signature vector uses synthetic values and is not a captured callback.

## Selection and merchant setup

SSLCOMMERZ was selected because one public specification covers the hosted flow,
server-side validation, transaction reconciliation and partial refund requests.
Sandbox registration is documented at
[the official registration page](https://developer.sslcommerz.com/registration/).
Actual account access has **not** been supplied or tested. Merchants need separate
store ID/password credentials per environment, HTTPS callback/IPN routes, merchant
panel IPN configuration and production refund IP registration. Account/channel
activation is an external prerequisite that SDK construction cannot verify.

The integration implements **BDT, non-physical goods, no shipping, no EMI**.
Currency conversion, physical shipping, specialized product profiles, Easy Checkout
JS, saved cards, subscriptions, standalone bKash and Nagad are outside this scope.
There is no separate server execution step in the supported hosted flow: initiation
returns a customer action URL; bank checkout is followed by server verification.

## Endpoint and state matrix

Base URLs: `https://sandbox.sslcommerz.com` and `https://securepay.sslcommerz.com`.
The client defaults to sandbox; production requires `sandbox=False`. TLS verification
and redirect refusal follow the existing transport policy. No custom endpoint or
cleartext opt-in is exposed for payments.

| Operation | Method/path | Important request/response rules | SDK interpretation |
| --- | --- | --- | --- |
| Initiation | POST `/gwprocess/v4/api.php` | Form credentials, `tran_id`, exact `total_amount`, explicit currency, customer/product fields and callback URLs; session/checkout URL on SUCCESS | Requires customer action; never paid |
| Validation | GET `/validator/api/validationserverAPI.php` | `val_id` plus credentials; compare merchant ID, both BDT amount/currency pairs and validation ID | VALID/VALIDATED paid; safe risk flag required to fulfill |
| Transaction query | GET `/validator/api/merchantTransIDvalidationAPI.php` | `tran_id`; preserve the complete `element` list and its count | All attempts retained, including duplicates; no implicit winner |
| Session query | GET same query path | `sessionkey`; returned session must match | Preserve pending, paid, failed or unknown |
| Refund initiation | **GET** same query path | `bank_tran_id`, mandatory `refund_trans_id` (introduced 2025-02-24), exact `refund_amount`, remarks and credentials | `success`/`processing` pending; not proof of refund completion |
| Refund query | GET same query path | `refund_ref_id`; match provider reference and expected bank ID | `refunded` complete, `processing` pending; other states unknown |

Checkout's documented BDT range is 10.00–500000.00. Refunds are positive amounts
up to the stored original payment; the application must enforce cumulative budgets.
Amounts use Decimal and never silently round or accept binary floats. SDK policy
requires HTTPS callbacks and a checkout URL on the configured gateway origin.
All required billing fields are supplied despite contradictory optionality wording
in the provider table. Unsupported application codes remain generic/unknown;
malformed envelopes fail closed. Negative/pending query results without sufficient
identity/amount fields may be rejected, never treated as confirmed payment.

## Notification verification

The supported signature is the provider's documented **MD5 parameter protocol**:
sorted signed form fields plus the MD5 store password digest. It is not a generic
HMAC scheme. No signature-disable option exists. Duplicate fields must be rejected
before collapsing a form to a dictionary; `parse_notification()` supplies a bounded
UTF-8 decoder. All decision fields must be signed. Signature verification is followed
by an authenticated server lookup against trusted application order data. Signed
failure/cancellation/expiry notifications are hints: the SDK queries current state
instead of overwriting a later verified payment. Risky or missing/unknown risk flags
hold fulfillment. Browser success URLs and raw callbacks cannot establish payment.

## Unresolved contracts and external verification

- **Authorized sandbox verification: NOT PERFORMED.** No account, credentials,
  checkout, charge or refund was used. Offline mocks certify SDK behavior only.
- The refund table describes `cancelled` as successful completion. Its meaning is
  contradictory; SDK keeps it unknown, retaining the application's reservation.
- A unique `tran_id`/`refund_trans_id` is a reference requirement, not documented
  provider-enforced idempotency. Duplicate handling, atomicity and retention are
  unverified; no side-effect replay is added.
- A refund timeout before a provider reference is received cannot be automatically
  reconciled through the documented refund-reference query. Keep it unknown and
  reserved; obtain gateway support/merchant evidence before further dispatch.
- Refund query responses do not document a returned amount. The example associates
  the provider reference with its durable reserved amount; this is not independent
  confirmation of the amount actually refunded. Channel limits, timing, cumulative
  enforcement and account-specific refund availability require authorized evidence.
- SHA-2 callback variants appear in some examples but lack a verified protocol here.
  They are unsupported; a SHA-2-only callback fails closed rather than bypassing
  verification. Merchant-specific current signature configuration needs confirmation.
- Exact empty-query/pending-error envelopes, other gateway origins and undocumented
  codes need sanitized account-specific evidence. Additional currencies remain
  disabled until conversion and amount validation are implemented and verified.

This audit does not complete the external verification gate for task 13. Do not add
sibling payment adapters or claim production readiness before resolving it.

## Remaining-gate re-audit (2026-10-10)

Re-read the official v4 and legacy specifications, the
[corporate integration document](https://sslcommerz.com/integration-document/), and
the [official Python implementation at commit 897c28e](https://github.com/sslcommerz/SSLCommerz-Python/blob/897c28e303e637e588829e5769e32b2ad77328f7/sslcommerz_lib/sslcommerz.py).
Repository inventory found no sanitized merchant captures, account-specific
verification record or provider support clarification. The existing contract fixture
is published-specification evidence with synthetic test data, not merchant evidence.
Only public documentation/source was retrieved; no payment API was contacted.

| Open contract | Audit result | Evidence needed to close it |
| --- | --- | --- |
| Actual merchant lifecycle | Registration instructions do not establish account access or successful checkout/refund operation | Authorized sandbox record linking initiation, IPN, validation, both query modes, partial refund and final refund state |
| Cancelled refund | Both developer specifications retain conflicting completion wording | Provider clarification of terminal meaning and whether funds moved, with matching sanitized refund query and merchant ledger evidence |
| Idempotency | Unique references and `processing` do not define duplicate-request atomicity, expiry or replay guarantees | Provider guarantee specifying key scope, retention, conflicting payloads and concurrent duplicates; observed duplicates alone cannot establish a guarantee |
| Refund timeout without reference | Published query requires `refund_ref_id`; `refe_id` is an optional reconciliation reference, not a documented query key | Supported lookup/reconciliation procedure using the stored merchant refund ID, or a documented operator procedure |
| Refunded amount and limits | Refund query has no amount/currency fields; account/channel limits and cumulative enforcement remain unspecified | Sanitized merchant refund ledger tied to bank/refund IDs and authoritative limits/settlement rules |
| SHA-2-only notifications | Official Python README includes `verify_sign_sha2`, but its implementation verifies MD5 `verify_sign` only | Provider algorithm, canonicalization/encoding rules, signed-field requirements and independent test vectors; a sample SHA-2 field is insufficient |
| Missing/empty/pending envelopes and checkout origins | Published examples do not establish all negative shapes or alternate trusted origins | Provenance-recorded responses for the supported BDT hosted profile and an authoritative origin policy |

Source precedence matters: v4's refund parameter table requires `refund_trans_id`
from February 2025, while its PHP sample, the corporate document and pinned Python
implementation omit it. Keep the explicit v4 requirement; older examples do not
justify removing it. Official examples also disable TLS verification in places;
Jukto retains certificate verification. IPN cancellation states and invoice/Quick
Bank Pay contracts do not define hosted refund status or idempotency guarantees.

For future evidence, record environment, API/profile/version, UTC timestamp,
authorization scope, HTTP method/path/status, response shape, source/capture origin
and stable pseudonymous identifiers linking the whole lifecycle. Keep exact
synthetic/non-personal amounts and statuses. Remove credentials, cookies, customer
details, card data and checkout URLs containing tokens before committing evidence.
Redacting a signed field invalidates its original signature: label such captures
as redacted schema evidence, and keep independently derived synthetic signature
vectors separate. Do not regenerate a signature and call it a captured callback.

Acceptance is **still open**. Public specifications cannot replace authorized
account-specific lifecycle verification, and no unsupported checkbox was closed.

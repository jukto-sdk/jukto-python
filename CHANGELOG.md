# Changelog

## Unreleased

No changes queued after the prepared alpha.

## 0.1.0a1 — Early access (prepared; publication pending)

First alpha for developer evaluation. APIs may change before a stable release.
Created and maintained by [Mehedi H Faysal](https://mahdiblogs.com).
Offline tests verify implementation behavior, not live provider compatibility.
SSLCOMMERZ is experimental; authorized merchant lifecycle verification is pending.
The [provider audit](https://jukto-sdk.github.io/jukto-python/provider-contracts/)
and [payment audit](https://jukto-sdk.github.io/jukto-python/payment-contracts/)
remain the source of verification limits.

### Correctness and security

- Audited AlphaSMS error codes; unknown BulkSMSBD classifications remain generic.
- Reject cleartext endpoints by default; verify TLS and refuse redirects.
- Metadata-only logs and withheld upstream exception text; raw data remains sensitive.
- Malformed/schema response errors and preserved GreenWeb partial/unknown batches.
- Pathao atomic token caching, process-local single-flight refresh and bounded replay;
  order POST replay is explicitly opt-in.
- Shipment validation before HTTP; provider-scoped routing and separate RedX goods value.

### Contracts and tooling

- Reusable owned or injected borrowed HTTP clients with explicit lifetime.
- Additive typed shipment/SMS results, options, capabilities, error metadata and
  reconciliation flags; preserve legacy raw methods and numeric inputs.
- Exact Decimal handling with documented unverified wire formats; packaged py.typed.
- Python 3.9–3.15 test/type/lint/wheel gates, branch-aware coverage and gated publication
  of the tested artifact for the immutable release commit and matching version/tag.
- Complete strict-built documentation, offline Django/FastAPI/fake-provider examples,
  provider verification matrix and contributor/security/compatibility guidance.
- Native asyncio clients for all six providers with shared sync/async contracts,
  owned/borrowed lifetime, cancellation-safe cleanup and Pathao single-flight refresh.
- Native FastAPI lifespan/dependency example with bounded in-flight requests.
- Scoped SSLCOMMERZ hosted BDT payment initiation, customer action, signature/server
  verification, complete transaction queries and partial refund request/query APIs.
- Shared sync/async payment contracts, exact money, safe risk holds and ambiguous
  side-effect metadata, including state-changing refund GET; no automatic replay.
- Durable SQLite entitlement/refund reservation example and offline lifecycle checks.
- Suppress credential-bearing HTTPX URL records only during SDK payment requests.
- bKash/Nagad remain planned. Sandbox/live verification is pending.

### Migration

Review the compatibility guide before adopting this alpha: BulkSMSBD
HTTP now requires an explicit insecure opt-in; unverified errors are generic;
malformed responses raise UnexpectedProviderResponseError; GreenWeb batches may
raise SMSBatchError; Pathao routing has no invented geography defaults and order
replay is disabled by default; RedX fields/auth/creation path were corrected.
No release was published as part of the implementation checklist. Provider
compatibility limitations remain in the contract audit.

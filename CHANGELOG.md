# Changelog

## Unreleased

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
- Describe payment and native asynchronous integrations as planned, not available.

### Migration

Review the compatibility guide before adopting the unreleased tree: BulkSMSBD
HTTP now requires an explicit insecure opt-in; unverified errors are generic;
malformed responses raise UnexpectedProviderResponseError; GreenWeb batches may
raise SMSBatchError; Pathao routing has no invented geography defaults and order
replay is disabled by default; RedX fields/auth/creation path were corrected.
No release was published as part of the implementation checklist. Provider
compatibility limitations remain in the contract audit.

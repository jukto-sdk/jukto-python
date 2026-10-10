# Compatibility and deprecation policy

## Public surface

The public surface consists of exports from `jukto`, documented constructors,
provider operations, result/options models and `JuktoError` metadata. Underscore
modules are internal. Raw response dictionaries and provider status labels follow
upstream schemas; they are not a stable cross-provider contract.

The SDK currently tests Python 3.9–3.15. Package metadata allows Python >=3.9;
future versions are not verified until added to CI. Optional framework versions
have their own Python/security lifecycles. Provider capability flags describe SDK
methods, not independent live-provider certification.

## Versioning and deprecation

Before 1.0, minor releases may change contracts; document public changes in the
changelog with migration steps. Patch releases should preserve the documented
public interface where practical. Deprecations should be documented and warned,
with at least a following minor release for migration where practical. Security
fixes or newly verified provider behavior may require immediate changes; describe
the exception and its impact. Do not silently discard unknown upstream states.

## Unreleased migration notes

- Legacy `create_order`, `check_status`, and `send_sms` remain raw APIs. Prefer
  `create_shipment`, `check_shipment_status`, and `submit_sms` for domain results.
- `status_code` is legacy/mixed; use `http_status` and `provider_error_code` separately.
- `response_body`, result `raw`, and batch evidence are sensitive. Error messages/logs
  do not expose raw details by default.
- BulkSMSBD's HTTP default now fails securely. Do not enable insecure HTTP without
  understanding the exposure; its HTTPS POST contract is unresolved.
- Unknown BulkSMSBD integer codes raise generic `ProviderError`; malformed responses
  raise `UnexpectedProviderResponseError`. GreenWeb batch exceptions preserve results.
- Pathao omits missing geography and disables order replay unless explicitly opted in.
  No default geographic ID or idempotency guarantee should be assumed.
- RedX creation uses `/parcel`, API-ACCESS-TOKEN, scoped area name/ID, and independent
  declared value. Its legacy raw tracking method remains unverified; the typed status
  method uses the documented parcel-info endpoint.
- Whole Decimal Pathao/Steadfast COD is exact; fractional Decimal COD is rejected.
  RedX Decimal wire text and weight units/types still need provider confirmation.
  Legacy numeric inputs remain accepted; avoid float for new monetary inputs.

Consult [the audit](provider-contracts.md) for exact evidence and open contracts.

## Native async (unreleased)

`Async*Client` classes are additive. Await operations and use `async with` or
`aclose()`; inject `httpx.AsyncClient`, not `httpx.Client`. Sync APIs retain their
behavior. Clients are scoped to one asyncio loop. See the [async guide](guides/async.md)
for ownership, cancellation and bounded concurrency. Provider verification gaps
apply to both interfaces. No release is published as part of this change.

## Hosted payments (unreleased)

`SSLCommerzClient`/`AsyncSSLCommerzClient` are additive and default to sandbox.
Existing SMS/logistics behavior is unchanged. The scoped BDT, non-physical hosted
flow requires exact Decimal amounts, HTTPS URLs and trusted stored references.
Read the [payment contract audit](payment-contracts.md): signatures do not bypass
server verification, refund GET is a financial side effect, and external sandbox
verification remains pending. No siblings or release were added.

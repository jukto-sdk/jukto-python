# Frequently asked questions

## Can I switch providers by changing one line?

The application can depend on `BaseLogisticsProvider` or `BaseSMSProvider` and
consume typed results. Provider accounts, geography, required fields and supported
features still differ. See [capabilities](provider-contracts.md#sdk-capabilities-and-verification-summary).

## Does Jukto classify every upstream error?

No. Documented codes receive audited mappings where evidence exists; unknown codes
remain generic and unexpected schemas raise `UnexpectedProviderResponseError`.
The [matrix](provider-contracts.md) records unresolved contracts. Programming
errors are not hidden by a blanket exception wrapper.

## Does Pathao always expire tokens after one hour?

The cache follows validated provider `expires_in`, not a fixed one-hour promise.
It uses a monotonic deadline, an expiry-dependent margin and process-local
single-flight refresh. Refresh outages propagate; only a classified rejected
refresh can trigger password fallback. Order replay after 401 is disabled unless
`retry_unauthorized_orders=True`; there is no verified idempotency guarantee.

## Does ACCEPTED or GreenWeb SENT mean delivered?

No. These represent submission output. Typed shipment polling currently retains
`UNKNOWN` plus the original provider status because polling vocabularies are not
verified. GreenWeb partial batches preserve every response entry; response indices
are not guaranteed to correspond to the original recipient list.

## Can FastAPI call these clients in async def?

Sync client calls block and need a sync route, thread-pool bridge or worker.
The alpha `Async*Client` classes support native awaited calls; see the
[async lifespan example](guides/async.md). Both examples manage provider cleanup.

## Can I use bKash, Nagad or SSLCommerz today?

The alpha includes one experimental SSLCOMMERZ hosted BDT flow,
including server verification and refund APIs. It is not sandbox/live certified.
Standalone bKash and Nagad clients remain planned. See the
[payment guide](guides/payments.md) and [contract audit](payment-contracts.md).

## Are the provider integrations production-certified?

No. Tests are offline. Published specification comparisons and unverified details
are recorded separately from actual live/sandbox transaction verification.

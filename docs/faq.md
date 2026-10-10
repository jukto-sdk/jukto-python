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

Calls block. Use a sync route, an explicit thread-pool bridge, or a background
worker. [The FastAPI example](guides/frameworks.md#fastapi) uses a sync route and
lifespan cleanup; it does not add native asynchronous SDK clients.

## Can I use bKash, Nagad or SSLCommerz today?

No. Payment integration is planned. There are no payment clients, execution,
webhook verification or refund APIs in this version.

## Are the provider integrations production-certified?

No. Tests are offline. Published specification comparisons and unverified details
are recorded separately from actual live/sandbox transaction verification.

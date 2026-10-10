# Native async clients (0.1.0a1 alpha)

The source tree provides `AsyncAlphaSMSClient`, `AsyncBulkSMSBDClient`,
`AsyncGreenWebClient`, `AsyncPathaoClient`, `AsyncRedXClient` and
`AsyncSteadfastClient`, exported from `jukto`. These additions have not been
published to PyPI by these tasks. `AsyncSSLCommerzClient` additionally supports
the scoped [hosted payment flow](payments.md); bKash/Nagad remain planned.

Use the same constructor configuration as the sync client, with an optional
borrowed `httpx.AsyncClient`. Await `send_sms`/`submit_sms`, `create_order`/
`create_shipment`, `check_status`/`check_shipment_status`, and Pathao's `get_token`
and `get_stores`. Results, input validation, error classifications, secure defaults
and unresolved provider contracts match sync clients. Async interfaces are
`AsyncBaseSMSProvider` and `AsyncBaseLogisticsProvider`; existing sync interfaces
and calls remain unchanged. There is no hidden event-loop bridge or thread offload.

```python
from jukto import AsyncAlphaSMSClient

async def submit(key: str):
    async with AsyncAlphaSMSClient(key) as provider:
        return await provider.submit_sms("01700000000", "Synthetic example")
```

The phone and message above are synthetic; calling this function with real
credentials sends a real request. Routine tests use `httpx.MockTransport` only.

## Lifetime and cancellation

These clients support **asyncio**, scoped to one event loop and worker. Trio is
not supported by Jukto's asyncio locks and cleanup even though HTTPX supports it.
Do not share providers across loops, processes or sync threads. Reuse one provider
for a worker's lifespan; avoid creating pools inside hot loops. `async with` or
`await provider.aclose()` closes an owned pool. Borrowed clients remain open and
must be closed by their owner. Cleanup waits for the owned client's `aclose()`
even if the cleanup caller is repeatedly cancelled, then propagates cancellation.
A cleanup error remains visible. Finish or cancel **and await** in-flight tasks
before closing the provider; concurrent shutdown with active requests is unsupported.

`asyncio.CancelledError` propagates unchanged. Cancellation during a refresh leaves
the previously cached token state intact, releases the token lock and lets another
caller refresh. Fully validated tokens publish atomically without a suspension.
An upstream server may nevertheless rotate a refresh token before cancellation
is observed locally. This cannot be rolled back; invalid-grant fallback follows the
same narrow rule as the sync client. The cache and single-flight lock are per
provider instance, not distributed across workers.

Cancellation after an SMS/shipment request begins may leave a completed upstream
operation. It does **not** establish failure and does not automatically retry.
Persist an application operation reference before dispatch and reconcile uncertain
outcomes before resubmission. The SDK does not provide durable storage or provider
enforced idempotency. Pathao replays a read once on 401; order replay still requires
`retry_unauthorized_orders=True` and remains an explicit, potentially duplicating
choice. No generic retries were added.

## FastAPI: native requests, bounded concurrency

This application creates one provider at lifespan startup, injects it through a
request dependency, awaits native HTTP and closes it at shutdown. Set
`JUKTO_ALPHA_API_KEY`, then run `uvicorn examples.async_fastapi_app:app` from the
checkout after installing the `examples` extra. Missing configuration fails startup.
Existing sync FastAPI examples remain valid.

```python
--8<-- "examples/async_fastapi_app.py"
```

`max_in_flight` limits submissions per worker; HTTPX `limits=` separately controls
pool connections, and `timeout=` bounds HTTP phases. A semaphore does not bound
queued requests, aggregate limits across processes, provide rate limiting or cap
total latency. Add ingress limits, queue deadlines, authentication and durable
reconciliation for production. Do not retry the entire GreenWeb batch after a
partial result. Sample error responses omit raw data and recipient details.

## Evidence and verification

Implementation follows [HTTPX async client and lifecycle guidance](https://www.python-httpx.org/async/)
(checked 2026-10-10). No new provider code, endpoint, success or idempotency claim
was introduced; the [provider matrix](../provider-contracts.md) applies equally to
both interfaces. Offline tests compare serialized requests, normalized results and
error metadata across all six providers, exercise AlphaSMS's recorded official
codes, malformed responses, partial outcomes, concurrent refresh, cancellation,
client ownership and bounded FastAPI requests. Mocks establish SDK behavior, not
live provider compatibility.

```bash
python -m pytest tests/test_async_providers.py --no-cov
```

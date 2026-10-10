---
title: "Architecture and resource ownership"
description: "Architecture and resource ownership for the Jukto Python SDK. Read implementation details, integration guidance and documented limitations."
---

# Architecture and resource ownership

Base provider interfaces separate application contracts from provider adapters.
Shared validation, HTTP mechanics and result models reduce repetition. Adapters
retain their own serialization, schema handling and code mappings. Strategy-based
injection simplifies tests; it does not promise identical provider capabilities.

## Transport lifetime

Each provider lazily creates one owned synchronous HTTPX client and reuses it.
`close()` is idempotent; closed providers cannot be reused. Context managers close
owned clients even on errors. Injecting `http_client=` borrows an existing client:
provider shutdown does not close it. The caller must close it after all borrowers
finish. Configure `timeout=` and owned pool `limits=` deliberately.

Do not close a shared provider while requests are active. FastAPI lifespan closes
after serving ends; the Django example uses a simpler request-owned scope, at the
cost of no pooling across requests. Multi-process workers have separate clients
and Pathao token caches; do not initialize network resources before forking.

Pathao uses process-local locking, monotonic expiry and atomic token replacement.
GET replay is bounded to one retry after 401; order POST replay requires explicit
`retry_unauthorized_orders=True`. No generic retry layer is added.

## Results and application boundaries

`Parcel`, provider options, capabilities and outcome models have annotations and
ship in a `py.typed` package. Raw JSON and provider statuses remain dynamic. SDK
capabilities describe available methods, not live certification or verified
upstream status semantics; see the [matrix](provider-contracts.md).

The [fake provider and framework examples](guides/frameworks.md) demonstrate
injection, client lifetime and error conversion. Native async adapters are planned;
all current provider HTTP operations block the calling thread.

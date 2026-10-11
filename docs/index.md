---
title: "Jukto Python SDK for Bangladesh SMS and Courier APIs"
description: "Integrate Bangladesh SMS and courier APIs with sync and async Python clients. Explore Jukto installation, provider guides and experimental SSLCOMMERZ payments."
---

# Jukto Python SDK

Jukto is an open-source sync and native asyncio SDK for Bangladesh SMS and logistics APIs,
created by [Mehedi H Faysal](https://mahdiblogs.com).
Version **0.1.0a1** is available on [PyPI](https://pypi.org/project/jukto/0.1.0a1/) for early-access evaluation.
APIs may change before a stable release. Offline tests do not certify live providers.
It provides shared interfaces, typed domain results and classifications for known
provider failures. Raw responses remain available, and unverified behavior stays
explicit in the [contract matrix](provider-contracts.md).

Adapters currently cover Steadfast, Pathao, RedX, GreenWeb, AlphaSMS and BulkSMSBD.
The alpha includes experimental [SSLCOMMERZ hosted BDT payments](guides/payments.md);
authorized merchant lifecycle verification remains open. Standalone bKash and Nagad
remain planned. Native asyncio clients are included; see the [async guide](guides/async.md). Provider
switching requires account/configuration and capability changes; typed models do
not erase provider-specific requirements or certify delivery semantics.

## Install

```bash
python -m pip install jukto==0.1.0a1
```

For source-only framework examples, clone the
repository, activate a virtual environment and install `-e '.[dev,examples]'`.
See [contributing](contributing.md) for the exact commands.

## Offline quickstart

Run `python -m examples.offline_quickstart` from the checkout. This source is
included directly and tested by pytest; it uses synthetic credentials and an
HTTPX MockTransport, so no provider connection occurs.

```python
--8<-- "examples/offline_quickstart.py"
```

Output is `accepted`, meaning submission acceptance, not delivery. For real
operations, obtain your own account configuration, read the provider's current
specification and preserve unknown/partial results before deciding to retry.

Continue with [logistics](guides/logistics.md), [SMS](guides/sms.md),
[framework examples](guides/frameworks.md) and [error handling](guides/errors.md).

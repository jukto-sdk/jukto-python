# Jukto (যুক্ত) Python SDK 🇧🇩

A sync and native async Python SDK for Bangladesh's SMS and courier APIs, created by
[Mehedi H Faysal](https://mahdiblogs.com).

[![PyPI](https://img.shields.io/pypi/v/jukto)](https://pypi.org/project/jukto/)
[![Documentation](https://img.shields.io/badge/docs-Jukto-blue)](https://jukto-sdk.github.io/jukto-python/)

[![CI](https://github.com/jukto-sdk/jukto-python/actions/workflows/ci.yml/badge.svg)](https://github.com/jukto-sdk/jukto-python/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/jukto-sdk/jukto-python/blob/main/LICENSE)

**Early access: 0.1.0a1.** APIs may change before a stable release. Offline tests
verify implementation behavior, not live provider compatibility. SSLCOMMERZ is
experimental and has not completed authorized merchant lifecycle verification.

## What it does

Jukto provides synchronous clients for Steadfast, Pathao, RedX, GreenWeb,
AlphaSMS and BulkSMSBD. Shared interfaces and typed result models reduce adapter
code; changing providers still requires their credentials, geography, required
fields and a review of supported capabilities. The SDK includes `py.typed`; raw
provider data remains dynamically typed.

Known HTTP/application errors become `JuktoError` subclasses. Malformed or
unrecognized responses raise `UnexpectedProviderResponseError`; undocumented
codes retain generic classifications. An accepted submission is not proof of
shipment or SMS delivery. Ambiguous outcomes require reconciliation before retry.

**Experimental SSLCOMMERZ hosted BDT payments are included in this alpha;**
see the [payment guide](https://jukto-sdk.github.io/jukto-python/guides/payments/) and [verification gaps](https://jukto-sdk.github.io/jukto-python/payment-contracts/).
Standalone bKash and Nagad remain planned. Native asyncio clients are included
for SMS, logistics and hosted payments; see the [async guide](https://jukto-sdk.github.io/jukto-python/guides/async/)
for lifecycle, cancellation and FastAPI usage. Existing sync clients still block.

| Provider | Client | Verification and setup |
| --- | --- | --- |
| Steadfast | `SteadfastClient` | API-Key/Secret-Key; wire contract remains unverified |
| Pathao | `PathaoClient` | OAuth2, store/geography; process-local refresh and bounded replay |
| RedX | `RedXClient` | API-ACCESS-TOKEN; separate declared value and RedX geography |
| GreenWeb | `GreenWebClient` | Token; preserves per-recipient partial/unknown outcomes |
| AlphaSMS | `AlphaSMSClient` | API key; published submission/error codes audited |
| BulkSMSBD | `BulkSMSBDClient` | Legacy HTTP default is rejected; HTTPS POST and codes unverified |

See the [provider contract and capability matrix](https://jukto-sdk.github.io/jukto-python/provider-contracts/)
for evidence dates and unresolved contracts. Offline tests are implementation
regressions, not live provider certification.

## Install and try it offline

```bash
python -m pip install jukto==0.1.0a1
```

The alpha is available on [PyPI](https://pypi.org/project/jukto/0.1.0a1/). Python 3.9+ is
required; CI covers 3.9–3.15. Explicitly pin the alpha version when evaluating it.

This standalone example works with the installed package and cannot send an SMS:

```python
import httpx
from jukto import AlphaSMSClient

def reply(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"error": 0, "data": {"request_id": 123}})

with httpx.Client(transport=httpx.MockTransport(reply)) as http_client:
    with AlphaSMSClient(api_key="synthetic-example-key", http_client=http_client) as provider:
        result = provider.submit_sms("01700000000", "Synthetic offline message")
    assert not http_client.is_closed  # Injected client stays caller-owned.

print(result.status.value)  # accepted means submitted, not delivered.
```

For source-only framework examples and contributor checks:

```bash
git clone https://github.com/jukto-sdk/jukto-python.git
cd jukto-python
python -m venv .venv
# Activate this environment using your shell, then:
python -m pip install -e '.[dev,examples]'
python -m examples.offline_quickstart
python -m pytest tests/test_documentation_examples.py --no-cov
```

The quickstart uses HTTPX MockTransport and synthetic data; it cannot send an SMS.
See [Django and FastAPI examples](https://jukto-sdk.github.io/jukto-python/guides/frameworks/) for configuration,
client lifetime, dependency injection and offline request tests. Production calls
require your own provider account and independent contract verification.

## Safety and lifecycle

Clients reuse an owned HTTP client and support `with`/`close()`. Injected clients
are borrowed and remain caller-owned. HTTPS and verified TLS are the defaults;
redirects are refused. Explicit `allow_insecure_http=True` permits legacy HTTP
and exposes credentials/content in cleartext; the quickstarts do not enable it.

Debug logs contain allowlisted metadata only. `response_body`, result `raw`, and
recipient evidence can contain secrets or personal data; do not log them. No
operation has a generic retry or automatic provider failover. See
[error and reconciliation guidance](https://jukto-sdk.github.io/jukto-python/guides/errors/).

## Documentation and contribution

- [Documentation site](https://jukto-sdk.github.io/jukto-python/)
- [Contributor guide](https://jukto-sdk.github.io/jukto-python/contributing/), [security policy](https://jukto-sdk.github.io/jukto-python/security/)
- [Compatibility and migration policy](https://jukto-sdk.github.io/jukto-python/compatibility/), [changelog](https://jukto-sdk.github.io/jukto-python/changelog/)
- [CI, measured coverage and release gates](https://jukto-sdk.github.io/jukto-python/ci-and-releases/)

Local checks:

```bash
python -m ruff check .
python -m mypy
python -m pytest
python -m mkdocs build --strict
```

## License

[MIT](https://github.com/jukto-sdk/jukto-python/blob/main/LICENSE) © 2026 Mehedi Hasan Faysal.

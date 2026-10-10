# Jukto (যুক্ত) Python SDK 🇧🇩

A Python SDK for Bangladesh's SMS and logistics APIs, created by
[Mehedi Hasan Faysal](https://github.com/MahdiBuilds), CTO of
[Feather IT](https://featherit.com).

[![CI](https://github.com/jukto-sdk/jukto-python/actions/workflows/ci.yml/badge.svg)](https://github.com/jukto-sdk/jukto-python/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

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

**SSLCOMMERZ hosted BDT payments are available in the unreleased source tree;**
see the [payment guide](docs/guides/payments.md) and [verification gaps](docs/payment-contracts.md).
Standalone bKash and Nagad remain planned. The unreleased source tree
adds native asyncio clients for SMS, logistics and hosted payments; see the [async guide](docs/guides/async.md)
for lifecycle, cancellation and FastAPI usage. Existing sync clients still block.

| Provider | Client | Verification and setup |
| --- | --- | --- |
| Steadfast | `SteadfastClient` | API-Key/Secret-Key; wire contract remains unverified |
| Pathao | `PathaoClient` | OAuth2, store/geography; process-local refresh and bounded replay |
| RedX | `RedXClient` | API-ACCESS-TOKEN; separate declared value and RedX geography |
| GreenWeb | `GreenWebClient` | Token; preserves per-recipient partial/unknown outcomes |
| AlphaSMS | `AlphaSMSClient` | API key; published submission/error codes audited |
| BulkSMSBD | `BulkSMSBDClient` | Legacy HTTP default is rejected; HTTPS POST and codes unverified |

See the [provider contract and capability matrix](docs/provider-contracts.md)
for evidence dates and unresolved contracts. Offline tests are implementation
regressions, not live provider certification.

## Install and try it offline

```bash
pip install jukto
```

The repository examples target the current source tree; a previously published
PyPI version may not include these unreleased changes. To exercise the quickstart:

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
See [Django and FastAPI examples](docs/guides/frameworks.md) for configuration,
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
[error and reconciliation guidance](docs/guides/errors.md).

## Documentation and contribution

- [Documentation site](https://jukto-sdk.github.io/jukto-python/)
- [Contributor guide](CONTRIBUTING.md), [security policy](SECURITY.md)
- [Compatibility and migration policy](docs/compatibility.md), [changelog](CHANGELOG.md)
- [CI, measured coverage and release gates](docs/ci-and-releases.md)

Local checks:

```bash
python -m ruff check .
python -m mypy
python -m pytest
python -m mkdocs build --strict
```

## License

[MIT](LICENSE) © 2026 Mehedi Hasan Faysal / Feather IT.

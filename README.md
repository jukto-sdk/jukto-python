# Jukto (যুক্ত) Python SDK

A modern, unified, open-source Python SDK connecting Bangladesh's fragmented third-party digital ecosystem (Logistics, SMS, Payments) into a single, elegant interface. Built on the **Strategy Pattern**, with complete typing, native debug logging, and standardized exception handling.

[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Coverage](https://img.shields.io/badge/coverage-98%25-brightgreen.svg)](#running-tests)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Supported Providers

| Category | Provider | Client Class | Auth Method |
| :--- | :--- | :--- | :--- |
| **Logistics** | Steadfast Courier | `SteadfastClient` | Api-Key & Secret-Key |
| **Logistics** | Pathao Courier | `PathaoClient` | OAuth2 (Auto-issue & refresh) |
| **Logistics** | RedX Logistics | `RedXClient` | Bearer Token |
| **SMS** | GreenWeb SMS | `GreenWebClient` | Token |
| **SMS** | AlphaSMS (sms.net.bd) | `AlphaSMSClient` | Api-Key |
| **SMS** | BulkSMSBD | `BulkSMSBDClient` | Api-Key & Sender-ID |

---

## Installation

```bash
pip install jukto
```

Or with `uv`:

```bash
uv add jukto
```

---

## Quickstart

### 1. Logistics: Steadfast, Pathao & RedX

```python
from jukto import SteadfastClient, PathaoClient, RedXClient, Parcel, JuktoError

# Define standard parcel model
parcel = Parcel(
    invoice_id="INV-98231",
    recipient_name="Rahim Uddin",
    recipient_phone="01712345678",
    recipient_address="House 12, Road 5, Dhanmondi, Dhaka",
    cod_amount=1250.0,
    note="Fragile items. Handle with care."
)

# 1. Steadfast Courier
sf = SteadfastClient(api_key="...", secret_key="...")
sf_order = sf.create_order(parcel)

# 2. Pathao Courier (automatic OAuth2 token lifecycle & proactive refreshing)
pathao = PathaoClient(
    client_id="...",
    client_secret="...",
    username="merchant@example.com",
    password="...",
    store_id=1234,
    sandbox=True
)
pathao_order = pathao.create_order(parcel)

# 3. RedX Logistics
redx = RedXClient(api_key="...", sandbox=True)
redx_order = redx.create_order(parcel)
```

---

### 2. SMS: GreenWeb, AlphaSMS & BulkSMSBD

```python
from jukto import GreenWebClient, AlphaSMSClient, BulkSMSBDClient, InsufficientBalanceError, JuktoError

# 1. GreenWeb SMS
gw = GreenWebClient(api_key="your_gw_token")
gw.send_sms(["01712345678"], "Your order is confirmed!")

# 2. AlphaSMS (sms.net.bd)
alpha = AlphaSMSClient(api_key="your_alpha_key", sender_id="FEATHER_IT")
alpha.send_sms("01712345678", "Your OTP is 492019")

# 3. BulkSMSBD
bulk = BulkSMSBDClient(api_key="your_bulksms_key", sender_id="FEATHER_IT")
bulk.send_sms("01712345678", "Welcome to Feather IT!")
```

---

## Debug Mode & Native Logging

Enable clean, formatted console logs with automatic credential masking:

```python
from jukto import enable_debug_logging, SteadfastClient

# Enable debug logs in development or scripts
enable_debug_logging()

client = SteadfastClient(api_key="my_key", secret_key="my_secret")
# Outbound requests and responses will be cleanly logged with credentials masked!
```

---

## Error Handling Guide

All SDK exceptions inherit from `JuktoError`:

```
JuktoError
│
├── JuktoValidationError          # Local validation errors (e.g. missing store_id)
├── JuktoConfigurationError       # Missing credentials / configs
│
└── ProviderError                 # Upstream provider failures
    ├── ProviderAuthenticationError  # 401/403 or invalid token
    ├── ProviderConnectionError      # Network drops, DNS resolution failure
    │   └── ProviderTimeoutError     # Request timed out
    ├── ProviderRateLimitError       # 429 Too Many Requests
    ├── ProviderServerError          # Upstream 5xx server errors
    ├── InvalidRequestError          # 400/422 validation failure on provider
    ├── ResourceNotFoundError        # 404 Consignment/parcel not found
    └── InsufficientBalanceError     # Account/SMS balance depleted
```

### Catching Errors Cleanly

```python
from jukto import SteadfastClient, Parcel, ProviderAuthenticationError, InsufficientBalanceError, JuktoError

try:
    client.create_order(parcel)
except ProviderAuthenticationError as err:
    print(f"Auth failed on {err.provider}: {err.message}")
except InsufficientBalanceError as err:
    print(f"Balance empty on {err.provider}: {err.message}")
except JuktoError as err:
    print(f"General error: {err}")
```

---

## Running Tests

Run the full offline test suite with coverage:

```bash
uv run pytest
```

Output:
```
68 passed in 0.74s (98% total coverage)
```

---

## Roadmap

- [x] **Phase 1: Foundation:** Git repository, Hatchling packaging, standard `src` layout, MIT license.
- [x] **Phase 2: Core Provider Development:**
  - [x] Steadfast Logistics
  - [x] Pathao Logistics (OAuth2 Lifecycle)
  - [x] RedX Logistics
  - [x] GreenWeb SMS
  - [x] AlphaSMS (sms.net.bd)
  - [x] BulkSMSBD
- [x] **Phase 3: Developer Experience (DX) & Error Handling:**
  - [x] Custom normalized exceptions (`jukto.exceptions`)
  - [x] Top-level exports (`from jukto import ...`)
  - [x] Native debug logging & payload masking (`jukto.logger`)
  - [x] Comprehensive developer documentation
- [x] **Phase 4: Testing & Quality Assurance:**
  - [x] Configured `pytest`, `pytest-httpx`, `respx`, and `pytest-cov`
  - [x] Offline mocking fixtures with **98% test coverage**
- [ ] **Phase 5: Publishing & CI/CD:**
  - [x] GitHub Actions test workflow (`.github/workflows/ci.yml`)
  - [x] GitHub Actions PyPI publishing workflow (`.github/workflows/publish.yml`)
  - [ ] Publish initial v0.1.0 release to PyPI
- [ ] **Future (V2 Scope):**
  - [ ] Payment Gateway Module (bKash, Nagad, SSLCommerz)
  - [ ] Async Client Support (`httpx.AsyncClient`)

---

## License

MIT © [Mehedi Hasan Faysal / Feather IT](https://github.com/jukto-sdk/jukto-python)

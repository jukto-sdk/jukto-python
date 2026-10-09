# Jukto (যুক্ত) Python SDK

A modern, unified, open-source Python SDK connecting Bangladesh's fragmented third-party digital ecosystem (Logistics, SMS, Payments) into a single, elegant interface. Built on the **Strategy Pattern**, with complete typing, native debug logging, and standardized exception handling.

[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Coverage](https://img.shields.io/badge/coverage-88%25-brightgreen.svg)](#running-tests)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Features

- **Standardized Strategy Pattern:** Swap providers (Steadfast to Pathao, GreenWeb to AlphaSMS) without touching application logic.
- **Normalized Exception Architecture:** Never catch raw `httpx.HTTPStatusError` again. Catch standardized exceptions like `ProviderAuthenticationError`, `InsufficientBalanceError`, or the root `JuktoError`.
- **OAuth2 Token Lifecycle Management:** `PathaoClient` handles automated login, token caching, and proactive expiration renewal.
- **Built-in Payload Masking & Debug Logger:** Native Python logging (`jukto.logger`) with automatic masking of API keys and passwords.
- **Bangla API Quirks Handled:** Normalizes vendor anomalies (HTTP 200 responses with error strings, non-zero error codes, and inconsistent keys).
- **Modern Python Typing:** Full type hints with `@dataclass` domain models and `from __future__ import annotations` compatibility down to Python 3.9+.

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

### 1. Logistics: Steadfast Courier

```python
from jukto import SteadfastClient, Parcel, JuktoError

client = SteadfastClient(
    api_key="your_steadfast_api_key",
    secret_key="your_steadfast_secret_key"
)

parcel = Parcel(
    invoice_id="INV-98231",
    recipient_name="Rahim Uddin",
    recipient_phone="01712345678",
    recipient_address="House 12, Road 5, Dhanmondi, Dhaka",
    cod_amount=1250.0,
    note="Fragile items. Handle with care."
)

try:
    response = client.create_order(parcel)
    print("Steadfast Order ID:", response["consignment"]["consignment_id"])
except JuktoError as e:
    print(f"Logistics Error: {e.message} (Status: {e.status_code})")
```

---

### 2. Logistics: Pathao Courier (with OAuth2 Auto-Management)

`PathaoClient` automatically acquires, caches, and refreshes OAuth2 tokens.

```python
from jukto import PathaoClient, Parcel, JuktoError

client = PathaoClient(
    client_id="your_client_id",
    client_secret="your_client_secret",
    username="merchant@example.com",
    password="your_password",
    store_id=1234,  # Default store
    sandbox=True    # Toggle sandbox vs production
)

parcel = Parcel(
    invoice_id="INV-PTH-001",
    recipient_name="Karim Khan",
    recipient_phone="01812345678",
    recipient_address="Mirpur 10, Dhaka",
    cod_amount=500.0,
    recipient_city=1,   # Dhaka
    recipient_zone=14,  # Mirpur
)

try:
    order = client.create_order(parcel)
    print("Pathao Consignment:", order["data"]["consignment_id"])
except JuktoError as e:
    print(f"Pathao Error: {e.message}")
```

---

### 3. SMS: GreenWeb SMS

```python
from jukto import GreenWebClient, JuktoError, InsufficientBalanceError

sms_client = GreenWebClient(api_key="your_greenweb_token")

try:
    result = sms_client.send_sms(
        phone_numbers=["01712345678", "01812345678"],
        message="Your Feather IT order has been confirmed!"
    )
    print("SMS Sent:", result)
except InsufficientBalanceError:
    print("Alert: GreenWeb SMS credits depleted! Please recharge.")
except JuktoError as e:
    print(f"SMS delivery failed: {e}")
```

---

### 4. SMS: AlphaSMS (sms.net.bd)

```python
from jukto import AlphaSMSClient, JuktoError, InsufficientBalanceError

client = AlphaSMSClient(api_key="your_alpha_key", sender_id="FEATHER_IT")

try:
    resp = client.send_sms("01712345678", "Your OTP is 123456")
    print("AlphaSMS Sent:", resp)
except InsufficientBalanceError:
    print("Alert: AlphaSMS balance is empty!")
except JuktoError as e:
    print(f"AlphaSMS failed: {e}")
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

---

## Running Tests

Run the full offline test suite with coverage:

```bash
uv run pytest
```

Output:
```
43 passed in 0.41s (88% total coverage)
```

---

## Roadmap

- [x] **Phase 1: Foundation:** Git repository, Hatchling packaging, standard `src` layout, MIT license.
- [x] **Phase 2: Core Provider Development:**
  - [x] Steadfast Logistics
  - [x] Pathao Logistics (OAuth2 Lifecycle)
  - [x] GreenWeb SMS
  - [x] AlphaSMS (sms.net.bd)
  - [ ] RedX Logistics
  - [ ] BulkSMSBD
- [x] **Phase 3: Developer Experience (DX) & Error Handling:**
  - [x] Custom normalized exceptions (`jukto.exceptions`)
  - [x] Top-level exports (`from jukto import ...`)
  - [x] Native debug logging & payload masking (`jukto.logger`)
  - [x] Comprehensive developer documentation
- [x] **Phase 4: Testing & Quality Assurance:**
  - [x] Configured `pytest`, `pytest-httpx`, `respx`, and `pytest-cov`
  - [x] Offline mocking fixtures with **88% test coverage**
- [ ] **Phase 5: Publishing & CI/CD:**
  - [ ] GitHub Actions test workflow
  - [ ] PyPI distribution build and release

---

## License

MIT © [Mehedi Hasan Faysal / Feather IT](https://github.com/jukto-sdk/jukto-python)

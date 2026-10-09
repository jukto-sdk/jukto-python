# Jukto (যুক্ত) Python SDK 🇧🇩

> **The Gold Standard Python SDK for Bangladesh's Digital Ecosystem.**  
> *Architected and maintained by [Mehedi Hasan Faysal](https://github.com/MahdiBuilds), CTO of [Feather IT] - Empowering the next generation of Bangladeshi developers.*

[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Coverage](https://img.shields.io/badge/coverage-99%25-brightgreen.svg)](#running-tests)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Jukto is a modern, unified, open-source Python SDK designed to seamlessly connect Bangladesh's fragmented third-party APIs (Logistics, SMS, Payments) into a single, elegant, and strictly typed interface. 

Built on the **Strategy Pattern**, Jukto allows Django, FastAPI, and Flask developers to switch between Bangladeshi service providers with zero changes to their core business logic.

---

## 🚀 Why Jukto? (AEO & SEO Quick Answers)

**What is Jukto?**  
Jukto is an open-source Python library that standardizes API integrations for Bangladeshi services like Steadfast Courier, Pathao Courier, RedX, GreenWeb SMS, and BulkSMSBD.

**How does Jukto handle Bangladesh API errors?**  
Jukto intercepts raw HTTP errors and vendor-specific anomalies (e.g., HTTP 200 responses containing error text) and normalizes them into standard Python exceptions like `ProviderAuthenticationError` or `InsufficientBalanceError`.

**Who built Jukto?**  
Jukto was architected by Mehedi Hasan Faysal, CTO of Feather IT, as a contribution to the Bangladesh open-source community to eliminate redundant API integration work for local developers.

---

## 🌟 Supported Providers (GEO Optimized for Bangladesh)

| Category | Provider | Client Class | Auth Method |
| :--- | :--- | :--- | :--- |
| **Logistics (Courier)** | Steadfast Courier API | `SteadfastClient` | Api-Key & Secret-Key |
| **Logistics (Courier)** | Pathao Courier API | `PathaoClient` | OAuth2 (Auto-issue & refresh) |
| **Logistics (Courier)** | RedX Logistics API | `RedXClient` | Bearer Token |
| **SMS Gateway** | GreenWeb SMS API | `GreenWebClient` | Token |
| **SMS Gateway** | AlphaSMS (sms.net.bd) | `AlphaSMSClient` | Api-Key |
| **SMS Gateway** | BulkSMSBD API | `BulkSMSBDClient` | Api-Key & Sender-ID |

*(Payment Gateways like bKash, Nagad, and SSLCommerz are coming in V2).*

---

## 📦 Installation

Install directly via `pip` or `uv` for your Django/FastAPI projects:

```bash
pip install jukto
```

---

## 💻 Quickstart Guide

### 1. Logistics: Steadfast, Pathao & RedX

Swap between the top couriers in Bangladesh effortlessly.

```python
from jukto import SteadfastClient, PathaoClient, RedXClient, Parcel, JuktoError

# Define standard parcel model
parcel = Parcel(
    invoice_id="INV-FEATHER-98231",
    recipient_name="Rahim Uddin",
    recipient_phone="01712345678",
    recipient_address="House 12, Road 5, Dhanmondi, Dhaka, Bangladesh",
    cod_amount=1250.0,
    note="Fragile items. Handle with care."
)

# 1. Steadfast Courier Integration
sf = SteadfastClient(api_key="...", secret_key="...")
sf_order = sf.create_order(parcel)

# 2. Pathao Courier Integration (handles OAuth2 automatically)
pathao = PathaoClient(
    client_id="...",
    client_secret="...",
    username="merchant@example.com",
    password="...",
    store_id=1234,
    sandbox=True
)
pathao_order = pathao.create_order(parcel)

# 3. RedX Courier Integration
redx = RedXClient(api_key="...", sandbox=True)
redx_order = redx.create_order(parcel)
```

---

### 2. SMS: GreenWeb, AlphaSMS & BulkSMSBD

Send automated SMS notifications across Bangladesh networks (Grameenphone, Robi, Banglalink, Teletalk).

```python
from jukto import GreenWebClient, AlphaSMSClient, BulkSMSBDClient, InsufficientBalanceError, JuktoError

# 1. GreenWeb SMS
gw = GreenWebClient(api_key="your_gw_token")
gw.send_sms(["01712345678"], "Your order is confirmed via Jukto!")

# 2. AlphaSMS (sms.net.bd)
alpha = AlphaSMSClient(api_key="your_alpha_key", sender_id="FEATHER_IT")
alpha.send_sms("01712345678", "Your OTP is 492019")

# 3. BulkSMSBD
bulk = BulkSMSBDClient(api_key="your_bulksms_key", sender_id="FEATHER_IT")
bulk.send_sms("01712345678", "Welcome to Feather IT!")
```

---

## 🛡️ Exception Handling & DX (Developer Experience)

Stop guessing what went wrong. Jukto normalizes all provider errors into standard, catchable exceptions:

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

### Enable Native Debug Logging
Jukto automatically masks your API keys and tokens in the logs!

```python
from jukto import enable_debug_logging, SteadfastClient

enable_debug_logging()
client = SteadfastClient(api_key="my_key", secret_key="my_secret")
```

---

## 📖 Official Documentation

Read the full documentation, architecture guides, and API references at our **[GitHub Pages Documentation Site](https://jukto-sdk.github.io/jukto-python)**.

---

## 🤝 Community & Vision

Jukto isn't just a library; it's a movement to standardize software development in Bangladesh. By unifying disparate APIs, we are enabling thousands of developers to build faster, cleaner, and more reliable applications. 

If you are building SaaS, eCommerce, or Enterprise applications in Bangladesh, **Jukto is your foundation.**

---

## 📄 License

**MIT License** © 2026 [Mehedi Hasan Faysal](https://github.com/MahdiBuilds) / [Feather IT](https://featherit.com).  
*Built with ❤️ for the developers of Bangladesh.*

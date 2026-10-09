# Project Jukto: Master Plan & Architecture Document

## 1. Executive Summary
**Project Name:** Jukto (BD-Connect)
**Objective:** Develop a robust, open-source Python SDK that unifies Bangladesh's fragmented digital ecosystem (Logistics, SMS, Payments) into a single, standardized interface.
**Target Audience:** 1,000+ Python developers (Django/FastAPI/Flask) in Bangladesh.
**Architecture Pattern:** Strategy Pattern (Interfaces vs. Adapters).

## 2. Technical Stack & Standards
* **Language:** Python (Developed on 3.14+, supporting >=3.9).
* **HTTP Client:** `httpx` (Synchronous implementation for V1, seamless transition to Async in V2).
* **Packaging:** `hatchling` (PEP 621 compliant via `pyproject.toml`).
* **Code Quality:** Fully typed (`typing`), strict modularity, clean error handling.

## 3. Core Architecture (The Strategy Pattern)
The SDK relies on strict separation between **Contracts** (Interfaces) and **Adapters** (Providers). This ensures developers can swap providers (e.g., Pathao to RedX) by changing a single line of code, without rewriting their application logic.

* **Interfaces (`src/jukto/interfaces/`)**: Abstract Base Classes defining strict data models (`dataclasses`) and required methods (`@abstractmethod`).
* **Providers (`src/jukto/providers/`)**: Concrete implementations of the interfaces handling external API routing, authentication, and error normalization.

## 4. Phase-by-Phase Roadmap

### Phase 1: Foundation (Completed)
- [x] Establish Git repository and organization (`jukto-sdk`).
- [x] Configure PyPI build system (`pyproject.toml`).
- [x] Setup standard `src` layout and open-source licensing (MIT).

### Phase 2: Core Provider Development (Active)
- **Logistics Module:**
  - [x] Define `BaseLogisticsProvider` and `Parcel` dataclass.
  - [x] Implement `SteadfastClient`.
  - [ ] Implement `PathaoClient`.
  - [ ] Implement `RedXClient`.
- **SMS Module:**
  - [x] Define `BaseSMSProvider``.
  - [x] Implement `GreenWebClient`.
  - [ ] Implement `AlphaSMSClient`.
  - [ ] Implement `BulkSMSBDClient`.

### Phase 3: Developer Experience (DX) & Error Handling (Active)
- [x] **Custom Exceptions:** Create `jukto.exceptions` (`JuktoError`, `ProviderAuthenticationError`, `InsufficientBalanceError`, `ProviderTimeoutError`, etc.) to catch and normalize errors from third-party endpoints.
- [x] **Top-Level Imports:** Expose core classes in the root `__init__.py` so developers can use `from jukto import SteadfastClient, GreenWebClient, Parcel, JuktoError`.
- [x] **Developer Documentation:** Comprehensive README guide with code examples and error-handling flowcharts.
- [ ] **Logging:** Implement a lightweight, native Python logger for tracking request/response payloads in development mode.

### Phase 4: Testing & Quality Assurance
- **Framework:** Implement `pytest`.
- **Mocking:** Use `pytest-httpx` or `respx` to mock external API calls, ensuring the test suite runs offline and does not consume actual provider credits.
- **Coverage:** Mandate 80%+ test coverage for all adapters before publishing.

### Phase 5: Publishing & CI/CD
- **Local Build Check:** Generate `.whl` and `.tar.gz` distributions.
- **PyPI Deployment:** Upload `v0.1.0` via Twine.
- **GitHub Actions:** Automate tests on every push to `main`, and automate PyPI publishing on GitHub Releases.

## 5. Future Scope (V2 Deliverables)
* **Payment Gateway Module:** Standardized interfaces for bKash, Nagad, and SSLCommerz.
* **Native Async Support:** Leveraging `httpx.AsyncClient` for high-throughput enterprise applications.

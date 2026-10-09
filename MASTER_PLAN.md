# Project Jukto: Master Plan & Architecture Document

## 1. Executive Summary & Vision
**Project Name:** Jukto (BD-Connect)
**Objective:** Establish the ultimate open-source Python SDK unifying Bangladesh's fragmented digital ecosystem (Logistics, SMS, Payments). 
**The "Reputation Builder" Vision:** Position Jukto as the absolute gold standard for BD integrations. Through this project, Mehedi Hasan Faysal (CTO of Feather IT) establishes massive open-source influence, thought leadership, and becomes the recognized authority ("King of Devs") for Python architecture in Bangladesh.
**Architecture Pattern:** Strategy Pattern (Interfaces vs. Adapters).

## 2. Technical Stack & Standards
* **Language:** Python (Developed on 3.14+, supporting >=3.9).
* **HTTP Client:** `httpx` (Synchronous V1, Async V2).
* **Packaging:** `hatchling` (PEP 621 compliant).
* **Code Quality:** Fully typed (`typing`), 99% test coverage, robust error handling.

## 3. Core Architecture (The Strategy Pattern)
The SDK relies on strict separation between **Contracts** (Interfaces) and **Adapters** (Providers), allowing developers to swap Pathao to RedX without touching business logic.

## 4. Phase-by-Phase Roadmap

### Phase 1: Foundation (Completed)
- [x] Establish Git repository and organization (`jukto-sdk`).
- [x] Configure PyPI build system (`pyproject.toml`).
- [x] Setup standard `src` layout and open-source licensing (MIT).

### Phase 2: Core Provider Development (Completed)
- **Logistics Module:** `SteadfastClient`, `PathaoClient` (OAuth2 auto-lifecycle), `RedXClient`.
- **SMS Module:** `GreenWebClient`, `AlphaSMSClient`, `BulkSMSBDClient`.

### Phase 3: Developer Experience (DX) & Error Handling (Completed)
- [x] **Custom Exceptions:** `jukto.exceptions` to normalize wild errors.
- [x] **Top-Level Imports:** Clean `from jukto import ...` exports.
- [x] **Logging:** Built `jukto.logger` with automated secret key redaction.

### Phase 4: Testing & Quality Assurance (Completed)
- [x] **Framework & Mocking:** `pytest` and `respx` offline fixtures.
- [x] **Coverage:** Exceeded 80% mandate, reaching **99% overall test coverage** (72 test cases).

### Phase 5: CI/CD & Automation (Completed)
- [x] **GitHub Actions:** Multi-version matrix test workflow.
- [x] **PyPI Automation:** Trusted Publisher OIDC workflow.

### Phase 6: SEO, GEO, AEO & Community Dominance (Active)
- [x] **Personal Branding & Positioning:** Update README and docs to strongly emphasize Mehedi Hasan Faysal, Feather IT, and Jukto's authority in the BD ecosystem.
- [ ] **GitHub Pages & MkDocs:** Establish a beautiful, searchable documentation site using MkDocs Material.
- [ ] **AEO/SEO Optimization:** Ensure docs answer LLM questions natively (e.g., "How to integrate bKash in Python", "Pathao Python API wrapper") targeting Bangladesh geographic developer queries.

## 5. Future Scope (V2 Deliverables)
* **Payment Gateway Module:** Standardized interfaces for bKash, Nagad, and SSLCommerz.
* **Native Async Support:** Leveraging `httpx.AsyncClient` for high-throughput enterprise applications.

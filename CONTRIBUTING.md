# Contributing to Jukto

Use a small, reviewable change with a concrete problem and regression evidence.
Read the provider contract matrix before changing classifications. Cite official
specifications or sanitized responses with provenance and a verification date;
existing mocks are not independent evidence. Keep unresolved contracts explicit.

## Local setup and checks

From a clone, create and activate a Python virtual environment, then run:

```bash
python -m pip install -e '.[dev,examples]'
python -m ruff check .
python -m mypy
python -m pytest
python -m mkdocs build --strict
python -m examples.offline_quickstart
python -m build
python -m twine check --strict dist/*
python scripts/release_gate.py
```

CI runs the supported Python matrix, framework request examples, branch-aware
coverage, strict docs and wheel-only checks. A passing mock is not provider
certification. Preserve meaningful regressions; do not exclude code to raise
coverage. Add executable examples to tests, preferably include their source into
docs so it cannot drift. Optional frameworks must not become runtime SDK dependencies.

## Pull requests

Reproduce behavior bugs before fixes. Explain the trigger, resulting behavior,
compatibility impact and checks run. Add migration notes and an Unreleased
changelog entry for public changes. Keep provider parsing in adapters; keep shared
HTTP mechanics small. Do not add generic retries for side effects without a
verified reconciliation/idempotency contract.

Routine tests must stay offline. Do not send SMS, create shipments, charge money,
publish releases or use production credentials for tests. Sandbox transactions
need explicit authorization and a separate record of what was verified. Never
include tokens, OTPs, subscriber numbers, addresses or unsanitized responses in
fixtures, issues or PRs. Use clearly synthetic data.

Report security issues privately using SECURITY.md. Regular bug reports should use
the sanitized issue template. Maintainers review contributions; a merged change
is not authorization to publish a release. Release/OIDC and external publisher
requirements are documented in the CI and releases guide.

## Documentation identity and discoverability

Use **Jukto (যুক্ত)** for the project and **Jukto Python SDK** for the Python
package documentation. Preserve author attribution to **Mehedi H Faysal** and
link to https://mahdiblogs.com. Keep provider names consistent with the contract
matrix, and distinguish released clients from planned ecosystem integrations.

Each documentation page should have a descriptive `title` and a unique,
accurate `description` in YAML front matter. Lead integration guides with the
problem solved and supported capabilities; retain verification limitations near
examples. Link related guides, API references and contract evidence naturally.
Do not add unsupported production claims, fabricated endorsements, keyword
lists in prose or ratings in structured data.

Run `python -m mkdocs build --strict` after editing documentation or the theme
in `docs/overrides/`. Check rendered canonical URLs, Open Graph metadata and
homepage JSON-LD. MkDocs generates `sitemap.xml` using `site_url`; update that
setting and verify redirects if the documentation moves. Search indexing and AI
citations are outcomes to monitor, not promises made by this metadata.

README and package metadata changes reach existing GitHub documentation when
merged; PyPI distribution metadata changes require a new version and release.
Never overwrite or retag an existing published version to update its description.

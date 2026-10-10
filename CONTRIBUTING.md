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

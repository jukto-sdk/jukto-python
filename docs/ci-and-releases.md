# CI and release gates

## Supported-version evidence

`checks.yml` is shared by pull requests, pushes to main, and release checks. It runs
correctness lint (Ruff E9/F63/F7/F82), mypy, the complete offline pytest suite,
branch coverage, distribution build, strict Twine metadata checks, and wheel-only
smoke checks on Python **3.9 through 3.15**. The package's `>=3.9` requirement is
preserved; future Python versions require adding a matrix entry and verification.
Python 3.9/3.10 are retained for compatibility despite upstream end of life.
The Python 3.9 development extra caps mypy below 1.20: [mypy 1.19 is the last
version runnable on Python 3.9](https://mypy.readthedocs.io/en/stable/changelog.html).
The [official Python downloads](https://www.python.org/downloads/) listed 3.15.0
as stable on 2026-10-10.

Each successful matrix job uploads `coverage-python-VERSION` (JSON and XML) and
`distributions-python-VERSION`. Download the coverage artifact from the linked
[CI run](https://github.com/jukto-sdk/jukto-python/actions/workflows/ci.yml) to see
measured statements, branches and missing paths. The README badge reports workflow
status; it does not claim a fixed coverage percentage.

Measured task-10 baseline on Python 3.14.7: 1,076/1,096 statements (98.18%) and
272/280 branches (97.14%), **97.97% combined coverage**. Pytest now enables branch
measurement and enforces **97% combined statement/branch coverage**, on every
matrix interpreter. This leaves less than one percentage point of headroom for
interpreter differences while rejecting meaningful coverage loss. It is not a
separate 97% branch-only floor. Changes must add behavioral regressions rather
than exclude code or chase percentages; providers remain unverified where the
[contract audit](provider-contracts.md) says so.

## Wheel isolation

The build makes an sdist, then builds the wheel from that sdist. Both pass strict
Twine checks and `scripts/release_gate.py`, including packaged `jukto/py.typed`.
A fresh virtual environment in a temporary directory installs only the wheel and
its runtime dependencies. After leaving the checkout, `python -I` runs the smoke
script: it ignores `PYTHONPATH` and source-path injection, checks the imported
package is under that environment and outside the checkout, verifies its version
and typing marker, and exercises an SDK operation using HTTPX MockTransport.
No provider traffic occurs.

## Publication dependency chain

Only a **published GitHub release** triggers `publish.yml`; ordinary pushes and
PRs cannot publish. The release tag is checked out and resolved once to a commit
SHA (including annotated tags). Every check and release-validation checkout uses
that SHA. Release validation downloads the exact immutable artifact tested by the
Python 3.14 matrix job, rather than rebuilding it, and requires:

- All supported-version checks to pass.
- Exactly one wheel and one sdist; matching project names and versions.
- A tag exactly `v` plus `project.version` in `pyproject.toml`, e.g. `v0.1.0`.
- A packaged typing marker and valid distribution metadata.

The publishing job depends on both `checks` and `build`, with GitHub's default
success condition. Failed, skipped, or cancelled dependencies prevent publication.
It downloads only the validated artifact from that same run; it does not check out
code or rebuild. Only this final job receives `id-token: write`, and it uses the
`pypi` environment. No API-token fallback is configured. Release tags should be
protected against replacement; old tags containing an older workflow do not gain
these gates retroactively. Package versions must be unique on PyPI; these checks
do not query PyPI for already-used versions. No release was published to test this
pipeline; offline regressions cover rejection and workflow dependency wiring.

## External configuration required before a real release

Repository YAML cannot prove account ownership or PyPI/GitHub settings. A project
owner must verify the [PyPI Trusted Publisher configuration](https://docs.pypi.org/trusted-publishers/using-a-publisher/)
for project `jukto`:

- GitHub owner: `jukto-sdk`.
- Repository: `jukto-python`.
- Workflow filename: `publish.yml` (not its display name).
- Environment: `pypi`, matching the workflow exactly.

Configure the GitHub `pypi` environment's allowed release tags and, where desired,
required reviewers; restrict who can publish releases and modify workflows. Verify
repository rules require the matrix checks before merging to main. A matching
Trusted Publisher, environment protections, tag protections and branch rules are
**external settings, not verified by this implementation**. OIDC acceptance and
actual upload remain untested because this task explicitly forbids publication.

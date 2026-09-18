# Test summary

## Local verification — 2026-09-17

| Check | Result |
|---|---|
| Pytest | 46 passed, 1 deselected PostgreSQL integration test |
| Branch-aware coverage | 96.86% (required: 95%) |
| Ruff format | passed |
| Ruff lint | passed |
| strict mypy | passed |
| pip-audit | no known vulnerabilities found |
| Runtime | CPython 3.12.14 on Windows |

The selected suite covers schemas, generation/splitting, property invariants, metrics, calibration,
artifacts, registry transactions and concurrency, canary routing, API authorization/error behavior,
drift reports, CLI behavior, performance budgets, and the complete lifecycle.

The PostgreSQL test is intentionally environment-gated locally. GitHub Actions provisions
PostgreSQL 18.6 and runs it separately. CI-generated `coverage.xml`, HTML coverage, and benchmark
JSON are uploaded per run so the evidence remains tied to a commit rather than represented as a
timeless checked-in claim.

One deprecation warning originates in the current Starlette test-client dependency's use of an
AnyIO compatibility alias; it does not change test behavior and is tracked through dependency
updates.

# Testing strategy

## Quality risks

The highest risks are data leakage, non-reproducible training, unsafe artifacts, silent state
corruption, unstable canary assignment, invalid input, misleading metrics, and unusable rollback.
Tests are organized around those behaviors rather than implementation trivia.

## Test layers

| Layer | Representative evidence |
|---|---|
| Schema/unit | strict bounds, timezone normalization, hashes, metrics, calibration, PSI |
| Property | randomized bounded observations and metric/distribution invariants with Hypothesis |
| Model | deterministic candidate documents, quality gates, calibration, abstention |
| Artifact security | content addressing, tamper/path traversal, shape and finite-value rejection |
| Registry | idempotency, concurrent registration, promotion, challenger, history, rollback |
| Service/API | readiness, auth, deterministic routing, prediction evidence, error mapping |
| End to end | generated data through cards, registry, champion/challenger, and critical drift |
| PostgreSQL | schema load, indexes, and lifecycle status constraint in a real CI service |
| Non-functional | training/inference budgets, 95% branch coverage, lint, strict types, audits |

## Local commands

```bash
python -m ruff format --check src tests scripts/validate-manifests.py
python -m ruff check src tests scripts/validate-manifests.py
python -m mypy
python -m pytest -m "not postgres"
python -m ml_observatory benchmark --report docs/reports/generated/benchmark.json
python scripts/validate-manifests.py
node scripts/validate-repository.mjs
node scripts/generate-code-index.mjs --check
```

The PostgreSQL test requires `OBSERVATORY_POSTGRES_DSN`. CI creates an isolated PostgreSQL 18.6
service and runs `python -m pytest -m postgres --no-cov`.

## Determinism

The generator, split, model seeds, candidate tie-break, canonical serialization, identifiers, and
canary routing are deterministic. Timing values are not compared byte for byte and use deliberately
generous upper budgets to reduce shared-runner noise.

## Promotion gates

The test fixture requires both candidates to be measured, verifies the selected candidate's ROC
AUC, recall, and subgroup-gap limits, and checks that lower Brier score determines the eligible
winner. These are demonstration gates, not universal production thresholds.

## Current result

See [test-summary.md](reports/test-summary.md). Generated HTML/XML coverage and benchmark JSON are
CI artifacts rather than committed output so evidence stays traceable to a workflow run.

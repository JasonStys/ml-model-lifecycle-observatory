# ML Model Lifecycle Observatory

[![CI](https://github.com/JasonStys/ml-model-lifecycle-observatory/actions/workflows/ci.yml/badge.svg)](https://github.com/JasonStys/ml-model-lifecycle-observatory/actions/workflows/ci.yml)
[![CodeQL](https://github.com/JasonStys/ml-model-lifecycle-observatory/actions/workflows/codeql.yml/badge.svg)](https://github.com/JasonStys/ml-model-lifecycle-observatory/actions/workflows/codeql.yml)

A production-minded, fully reproducible machine-learning lifecycle built around an intentionally
small prediction problem: estimate whether a **synthetic software service** will fail within 24
hours. The point is not a flashy accuracy claim. It is the engineering around the model—data and
artifact provenance, calibration, independent evaluation, promotion gates, deterministic canary
routing, drift evidence, rollback, and safe serving.

No employer, customer, personal, or production data is included. Every observation is generated
locally from a documented seeded simulator.

## What this demonstrates

- Deterministic Python training for a logistic baseline and compact neural network.
- A disjoint train/calibration/test protocol, Platt-style probability calibration, F2 threshold
  selection, ROC AUC, Brier score, log loss, ECE, abstention, and subgroup recall-gap checks.
- Content-addressed, non-executable JSON model artifacts verified by SHA-256 before inference.
- A transactional SQLite registry with candidate/champion/retired states and immutable audit
  events, plus a PostgreSQL schema analogue exercised in CI.
- Champion/challenger serving, stable request-based canary routing, shadow prediction capture,
  promotion, and rollback.
- PSI drift monitoring, machine-readable evidence, model and dataset cards, a FastAPI service,
  Docker/Compose, hardened Kubernetes manifests, and conservative performance budgets.
- Strict typing, linting, property tests, concurrency tests, 95% coverage enforcement, dependency
  auditing, CodeQL, dependency review, and pinned automation dependencies.

## Architecture at a glance

```text
seeded generator -> schema validation -> train / calibrate / locked test
                                           |
                        logistic + compact MLP candidates
                                           |
                    quality gates -> content-addressed JSON artifacts
                                           |
                  transactional model registry + audit history
                                           |
            FastAPI -> champion / deterministic canary / shadow challenger
                                           |
                        prediction evidence + PSI drift reports
                                           |
                                  audited rollback
```

The detailed component and trust-boundary view is in [docs/architecture.md](docs/architecture.md).

## Quick start

Requires Python 3.12–3.14. The commands below use a virtual environment and the exact reviewed
dependency set.

```bash
python -m venv .venv
source .venv/bin/activate             # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
python -m ml_observatory demo --workspace .artifacts/demo --count 1200
python -m ml_observatory inspect --registry .artifacts/demo/registry.sqlite3
```

The demo produces a dataset and metadata, two portable model artifacts, a populated registry,
candidate evaluation, model/dataset cards, and a deliberately shifted critical drift report.

To serve the demo, point the API at its registry and artifact directory:

```bash
export OBSERVATORY_REGISTRY_PATH=.artifacts/demo/registry.sqlite3
export OBSERVATORY_ARTIFACT_ROOT=.artifacts/demo/models
export OBSERVATORY_ADMIN_TOKEN=replace-with-a-secret
python -m ml_observatory serve --host 127.0.0.1 --port 8000
curl http://127.0.0.1:8000/health/ready
curl -H 'Content-Type: application/json' \
  --data @examples/predict-request.json http://127.0.0.1:8000/v1/predict
```

Interactive OpenAPI documentation is available at `http://127.0.0.1:8000/docs`.

## Verification

```bash
bash scripts/verify.sh
```

The committed local verification result is **46 passed, 1 environment-gated PostgreSQL test,
96.86% branch-aware coverage**, with Ruff, strict mypy, and the dependency audit clean. CI also starts PostgreSQL 18.6,
validates container/orchestration assets, audits the lock file, builds the image, and uploads
coverage and benchmark evidence. See [docs/reports/test-summary.md](docs/reports/test-summary.md)
and [docs/reports/validation.md](docs/reports/validation.md).

## Safety and scope

This is an educational portfolio system, not an autonomous production decision engine. The
included model is trained only on synthetic data. Authentication is a deliberately narrow
shared-token example and must be replaced with managed identity and authorization in a real
deployment. SQLite is intentionally limited to one API replica; use the PostgreSQL design or an
external registry before scaling writers. See [docs/risk-register.md](docs/risk-register.md).

## Repository guide

| Area | Responsibility |
|---|---|
| `src/ml_observatory/` | contracts, training, evaluation, artifacts, registry, service, API, CLI |
| `tests/` | unit, property, integrity, concurrency, API, lifecycle, and PostgreSQL checks |
| `sql/` | transactional SQLite and PostgreSQL registry schemas |
| `deploy/kubernetes/` | hardened single-writer demonstration deployment |
| `scripts/` | one-command verification, demo, manifest checks, and documentation invariants |
| `docs/` | architecture, API, lifecycle, risks, research, operations, and evidence |
| `.github/` | CI, CodeQL, dependency review, and Dependabot configuration |

The per-file purpose map is in [docs/file-catalog.md](docs/file-catalog.md), and exact class,
function, table, and important-constant locations are generated in
[docs/code-index.md](docs/code-index.md).

## Documentation

- [Architecture](docs/architecture.md)
- [Model lifecycle](docs/model-lifecycle.md)
- [API contract](docs/api.md)
- [Data contract](docs/data-contract.md)
- [Operations and rollback](docs/operations.md)
- [Testing strategy](docs/testing.md)
- [Complexity analysis](docs/complexity.md)
- [Research basis](docs/research.md)
- [Risk register](docs/risk-register.md)
- [Architecture decision record](docs/adr/0001-portable-artifacts-and-small-registry.md)

## License

[MIT](LICENSE)

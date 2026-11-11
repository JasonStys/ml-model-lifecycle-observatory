# ML Model Lifecycle Observatory

## Native model workbench

Version 1.1.0 adds an actual Windows desktop application over this repository's model,
artifact, registry and inference implementation. Its full application includes editable JSON
Lines data, import/validation, training of both supported algorithms, registry inspection,
hash-verified review, explicit promotion, shadow/canary assignment, prediction, PSI drift,
verified rollback and new-file JSON evidence export. Prepared service-health observations
are editable data inside the workbench; selecting them does not save or train anything.

The complete portable directory bundles Python 3.14.10, Tcl/Tk and the scientific libraries.
Extract the whole Windows ZIP and launch `MLModelLifecycleObservatory.exe`; no Python,
terminal, IDE, Docker or API account is required by that application. This is an unsigned
Windows x64 candidate, not an independently signed installer or an Android/macOS release.
Publication and installation are separate from the source/native acceptance checks.

Your identified, locked OS-local workspace retains the dataset, SQLite registry, model
artifacts and deployment history outside the extracted application. The UI explains its
single trusted OS-owner boundary; it does not start the web API or provide account isolation.
Use synthetic, approved data. Start with [native usage and recovery](docs/native-application.md)
and [observed native validation](docs/reports/native-application-2026-11-11.md).

## Read-only release review

Operators can generate a **verified model-review dossier** before making a separate lifecycle decision. Run `python -m ml_observatory.cli review MODEL_ID --registry PATH --artifact-root PATH --report NEW.json`, optionally adding `--drift-report PATH` for a matching bounded JSON drift report. The command verifies the content-addressed bundle and agreement with registered algorithm/dataset/evaluation metadata, exposes recorded quality gates and failed reasons, calibration/abstention settings, train/calibration/test counts, current champion/challenger roles and bounded promotion history.

Drift context shows sample counts, feature/threshold consistency and a small-sample review flag. Missing drift is explicitly “not supplied”; neither passed gates nor observed drift automatically promotes a model. A prior rollback candidate remains unverified context. The report distinguishes artifact/metadata verification from raw dataset verification and fresh metric evaluation. Export refuses existing files. An authenticated `GET /v1/admin/models/{id}/review` supplies the core dossier through the existing constant-time admin-token boundary without accepting server filesystem paths. See [review workflow](docs/release-review.md) and [validation](docs/reports/practical-workflows-20261109.md).

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

The earlier committed local verification result is **46 passed, 1 environment-gated PostgreSQL test,
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

| Area                  | Responsibility                                                                  |
| --------------------- | ------------------------------------------------------------------------------- |
| `src/ml_observatory/` | contracts, training, evaluation, artifacts, registry, service, API, CLI         |
| `tests/`              | unit, property, integrity, concurrency, API, lifecycle, and PostgreSQL checks   |
| `desktop/`            | native authoring, original-core adapters, retained worker and profile lifecycle |
| `native_tests/`       | actual Tk control, close and layout acceptance in synthetic profiles            |
| `sql/`                | transactional SQLite and PostgreSQL registry schemas                            |
| `deploy/kubernetes/`  | hardened single-writer demonstration deployment                                 |
| `scripts/`            | one-command verification, demo, manifest checks, and documentation invariants   |
| `docs/`               | architecture, API, lifecycle, risks, research, operations, and evidence         |
| `.github/`            | CI, CodeQL, dependency review, and Dependabot configuration                     |

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
- [Native application](docs/native-application.md)
- [Architecture decision record](docs/adr/0001-portable-artifacts-and-small-registry.md)
- [Latest maintenance audit](docs/reports/maintenance-audit-2026-09-18.md)

## License

[MIT](LICENSE)

## Documentation editions

Start with the [organized handbook](docs/handbook.md) for current usage, design, security and test guidance. Reviewed downloadable editions: [project-guide.docx](docs/reports/project-guide.docx).

[Publication identities and source scope](docs/reports/publications.json) · [Documentation validation record](docs/reports/documentation-refresh-2026-11-09.md). Historical results retain their own tested revision and date.

## Current Windows application guide

The published **1.1.0** app has a [four-page illustrated guide](docs/reports/windows-application-guide-1.1.0.docx) with actual installed screenshots, a worked user journey, important source excerpts and operating limits. Read the [dated validation report](docs/reports/installed-windows-2026-11-11.md) and [byte/page review manifest](docs/reports/windows-application-guide-1.1.0.json) for exact scope. Historical documentation editions remain unchanged.

Added files:

- [docs/reports/windows-application-guide-1.1.0.docx](docs/reports/windows-application-guide-1.1.0.docx): source-specific installed-app workflow, screenshots, code and measured validation.
- [docs/reports/windows-application-guide-1.1.0.json](docs/reports/windows-application-guide-1.1.0.json): document, screenshot, immutable-source and reviewed-page hashes.
- [docs/reports/installed-windows-2026-11-11.md](docs/reports/installed-windows-2026-11-11.md): observed results, installation, data handling and remaining limits.

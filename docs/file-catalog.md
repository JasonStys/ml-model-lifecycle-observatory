# File catalog

Every authored file is summarized here. Exact class, function, table, and important-constant
locations are generated in [code-index.md](code-index.md).

## Root and automation

| File                                      | Purpose                                                                               |
| ----------------------------------------- | ------------------------------------------------------------------------------------- |
| `.editorconfig`                           | Cross-editor whitespace and newline conventions.                                      |
| `.env.example`                            | Names the three supported runtime environment variables without a live secret.        |
| `.gitattributes`                          | Normalizes text files and marks generated evidence appropriately.                     |
| `.gitignore`                              | Excludes environments, caches, credentials, coverage, and runtime artifacts.          |
| `.github/dependabot.yml`                  | Schedules bounded Python, Docker, and Actions update proposals.                       |
| `.github/workflows/ci.yml`                | Runs Python, PostgreSQL, repository, manifest, benchmark, audit, and image checks.    |
| `.github/workflows/codeql.yml`            | Performs Python semantic security analysis on changes and weekly.                     |
| `.github/workflows/dependency-review.yml` | Rejects high-severity dependency changes in pull requests.                            |
| `compose.yaml`                            | Runs one hardened API container with persistent demonstration data.                   |
| `CONTRIBUTING.md`                         | Defines development, documentation, test, and review expectations.                    |
| `Dockerfile`                              | Builds the pinned non-root API image.                                                 |
| `LICENSE`                                 | MIT license terms.                                                                    |
| `pyproject.toml`                          | Package metadata, dependency ranges, CLI entry point, and tool policy.                |
| `README.md`                               | Project overview, architecture, quick start, evidence, limits, and documentation map. |
| `requirements.lock`                       | Exact reviewed runtime and verification dependency set.                               |
| `SECURITY.md`                             | Private reporting guidance, trust boundaries, and implemented controls.               |

## Application

| File                               | Purpose                                                                            |
| ---------------------------------- | ---------------------------------------------------------------------------------- |
| `src/ml_observatory/__init__.py`   | Exposes package identity and version.                                              |
| `src/ml_observatory/__main__.py`   | Enables `python -m ml_observatory`.                                                |
| `src/ml_observatory/api.py`        | FastAPI health, inference, registry, promotion, challenger, and rollback routes.   |
| `src/ml_observatory/artifacts.py`  | Writes and validates content-addressed portable model documents.                   |
| `src/ml_observatory/cli.py`        | Demo, benchmark, inspection, lifecycle mutation, and server commands.              |
| `src/ml_observatory/config.py`     | Reads explicit registry, artifact, and admin-token settings.                       |
| `src/ml_observatory/data.py`       | Generates, hashes, stores, describes, splits, and vectorizes synthetic data.       |
| `src/ml_observatory/drift.py`      | Computes per-feature PSI and aggregate drift state.                                |
| `src/ml_observatory/evaluation.py` | Implements metrics, thresholds, abstention, groups, and reference histograms.      |
| `src/ml_observatory/hashing.py`    | Supplies canonical JSON, SHA-256, atomic write, and safe path resolution.          |
| `src/ml_observatory/lifecycle.py`  | Orchestrates the reproducible end-to-end demonstration and reports.                |
| `src/ml_observatory/py.typed`      | Declares that the installed package ships type information.                        |
| `src/ml_observatory/registry.py`   | Owns transactional model state, deployment history, audits, and prediction events. |
| `src/ml_observatory/reports.py`    | Renders JSON/Markdown dataset, model, and drift evidence.                          |
| `src/ml_observatory/schemas.py`    | Defines strict input, output, dataset, and drift contracts.                        |
| `src/ml_observatory/service.py`    | Loads verified deployments, routes requests, predicts, and records evidence.       |
| `src/ml_observatory/training.py`   | Fits, calibrates, evaluates, serializes, and selects two model candidates.         |

## Schemas, deployment, scripts, and examples

| File                                | Purpose                                                                        |
| ----------------------------------- | ------------------------------------------------------------------------------ |
| `sql/schema.sql`                    | SQLite model, deployment, history, audit, and prediction schema.               |
| `sql/postgres/schema.sql`           | PostgreSQL analogue used for integration validation.                           |
| `deploy/kubernetes/deployment.yaml` | Single-replica hardened pod, probes, resources, secret reference, and volumes. |
| `deploy/kubernetes/service.yaml`    | Internal ClusterIP exposure for the API.                                       |
| `examples/predict-request.json`     | Complete valid prediction request for curl or OpenAPI.                         |
| `scripts/demo.sh`                   | Runs and inspects a complete local lifecycle.                                  |
| `scripts/generate-code-index.mjs`   | Generates exact source declaration locations.                                  |
| `scripts/validate-manifests.py`     | Parses deployment YAML and enforces safety invariants.                         |
| `scripts/validate-repository.mjs`   | Checks required docs, links, and source headers.                               |
| `scripts/verify.sh`                 | Executes the full local quality and evidence gate.                             |

## Documentation and reports

| File                                                     | Purpose                                                                      |
| -------------------------------------------------------- | ---------------------------------------------------------------------------- |
| `docs/architecture.md`                                   | Component responsibilities, trust boundaries, deployment, and failures.      |
| `docs/adr/0001-portable-artifacts-and-small-registry.md` | Records artifact/registry alternatives and the selected trade-off.           |
| `docs/api.md`                                            | HTTP routes, contracts, authentication, response semantics, and limits.      |
| `docs/code-index.md`                                     | Generated class/function/table/constant locations.                           |
| `docs/complexity.md`                                     | Big-O and bounded performance analysis.                                      |
| `docs/data-contract.md`                                  | Feature schema, provenance, split rules, privacy, and limitations.           |
| `docs/file-catalog.md`                                   | Summarizes every authored repository file.                                   |
| `docs/model-lifecycle.md`                                | Explains generation through evaluation, promotion, monitoring, and rollback. |
| `docs/operations.md`                                     | Startup, routine checks, incidents, rollback, and backup runbook.            |
| `docs/research.md`                                       | Connects primary references to concrete design choices.                      |
| `docs/risk-register.md`                                  | Maps implemented and residual risks to accountable functions.                |
| `docs/testing.md`                                        | Risk-based test layers, determinism, commands, and promotion gates.          |
| `docs/reports/benchmark.md`                              | Defines performance workload, budgets, and interpretation.                   |
| `docs/reports/test-summary.md`                           | Captures the local test and coverage result.                                 |
| `docs/reports/validation.md`                             | Summarizes completed, CI-only, and explicitly unclaimed validation.          |
| `docs/reports/generated/.gitkeep`                        | Preserves the ignored runtime-evidence directory.                            |

## Tests

| Added file                                     | Purpose                                                                             |
| ---------------------------------------------- | ----------------------------------------------------------------------------------- |
| `src/ml_observatory/review.py`                 | Bounded verified release dossier, explicit gates, drift context and interpretation. |
| `tests/test_review.py`                         | Independent arithmetic plus actual artifact/registry/CLI/API non-mutating journeys. |
| `docs/release-review.md`                       | Operator workflow, evidence semantics, bounds and limits.                           |
| `docs/reports/practical-workflows-20261109.md` | Dated validation and resource-handle repair evidence.                               |

| File                                    | Purpose                                                                 |
| --------------------------------------- | ----------------------------------------------------------------------- |
| `tests/conftest.py`                     | Creates deterministic shared training and deployment fixtures.          |
| `tests/test_api.py`                     | Verifies health, request, authorization, and lifecycle HTTP behavior.   |
| `tests/test_cli.py`                     | Verifies parsing, output, registry commands, serving, and budgets.      |
| `tests/test_data_schemas.py`            | Verifies contracts, generation, metadata, storage, and splits.          |
| `tests/test_drift_reports_lifecycle.py` | Verifies PSI, report output, settings, and end-to-end demo.             |
| `tests/test_evaluation.py`              | Verifies metrics, thresholds, abstention, subgroups, and histograms.    |
| `tests/test_postgres.py`                | Loads real PostgreSQL DDL and checks indexes/constraints in CI.         |
| `tests/test_registry_service.py`        | Verifies concurrent state, routing, logging, promotion, and rollback.   |
| `tests/test_training_artifacts.py`      | Verifies reproducibility, quality gates, safe artifacts, and inference. |

## Reviewed documentation editions

## Native application additions

| File                                            | Purpose                                                                                                |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `desktop/__init__.py`                           | Identifies the native presentation package.                                                            |
| `desktop/workspace.py`                          | Bounds approved data, retains profile ownership and invokes original model/registry operations.        |
| `desktop/application.py`                        | Genuine Tk data editors, registry/deployment controls, prediction, drift, evidence and help.           |
| `desktop/launcher.py`                           | Frozen identity, explicit profile selection, runtime inspection and completion-aware window lifecycle. |
| `desktop/acceptance.py`                         | Marked synthetic real-native control and restart proof, including own-window captures.                 |
| `native_tests/test_widgets.py`                  | Real control/input/confirmation/busy-close/layout journeys.                                            |
| `tests/test_native_workspace.py`                | Actual scientific/lifecycle/durable-state and negative input/artifact contracts.                       |
| `tests/test_native_identity.py`                 | Strict package identity and synthetic marker/output refusal regressions.                               |
| `tests/test_native_archive.py`                  | Real ZIP safety, byte budgets, exclusive writes and exact Windows marker protocol.                     |
| `scripts/build-native.py`                       | Source-bound patched-runtime Windows application, authored icon and dependency notices.                |
| `scripts/archive_native.py`                     | Fresh portable archive/sidecar, bounded relocation and actual extracted-app acceptance.                |
| `requirements-native.lock`                      | Exact isolated native packaging tools.                                                                 |
| `.github/workflows/native-app.yml`              | Real Windows build/control/package journeys; bounded evidence and explicit package opt-in.             |
| `docs/native-application.md`                    | Native usage, files, privacy, limits, recovery and build instructions.                                 |
| `docs/reports/native-application-2026-11-11.md` | Observed local native/core checks and honestly retained prototype failures.                            |
| `docs/images/native-registry.png`               | Actual synthetic bundled-app registry screenshot.                                                      |
| `docs/images/native-dossier.png`                | Actual synthetic bundled-app verified evidence screenshot.                                             |

## Reviewed documentation editions (historical source)

| File                                               | Purpose                                                                  |
| -------------------------------------------------- | ------------------------------------------------------------------------ |
| `docs/handbook.md`                                 | Organized usage, implementation, security and evidence navigation.       |
| `docs/reports/project-guide.docx`                  | Reviewed source-bound Word project guide with dated evidence and limits. |
| `docs/reports/publications.json`                   | Exact publication hashes, source identity and page review receipts.      |
| `docs/reports/documentation-refresh-2026-11-09.md` | Actual documentation integration checks and interpretation limits.       |

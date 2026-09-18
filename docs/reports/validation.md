# Validation report

## Scope

Validation covers source quality, model/data contracts, lifecycle correctness, security boundaries,
documentation integrity, deployment manifests, and reproducible automation.

## Completed evidence

- Python formatting and the selected security/correctness/performance lint rules pass.
- Strict mypy passes for all package modules.
- 46 local tests pass with 96.86% branch-aware coverage against a 95% gate.
- The exact dependency lock returns no known vulnerabilities from `pip-audit`.
- Deterministic training generates byte-identical model documents for the same inputs and versions.
- Both candidates clear the fixture's quality gates; the logistic candidate wins on Brier score.
- Artifact tests reject tampering, traversal, schema/shape failures, and non-finite values.
- Registry tests cover concurrent idempotent registration, atomic promotion, challenger rules,
  stable routing, audit evidence, and rollback.
- The end-to-end demo emits dataset/model cards, candidate metrics, a champion and challenger, and
  a deliberately critical PSI report without external data/services.
- Repository validation checks required docs, local links, source headers, and generated code-index
  freshness. Kubernetes validation checks immutable tag, probes, non-root/read-only execution, and
  disabled privilege escalation.

## CI-only evidence

GitHub Actions installs the lock on Python 3.13, reruns the full gate, executes PostgreSQL 18.6
integration, audits dependencies, validates Compose, builds the hardened container, and runs
CodeQL. Dependency review is configured for pull requests.

## Honest limitations

No real-world predictive validity, distributed registry operation, production load capacity,
external identity, object-store integration, or monitoring backend is claimed. The Kubernetes
volume is ephemeral and the manifest intentionally requests one replica. These boundaries are
documented in architecture, operations, and the risk register.

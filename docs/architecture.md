# Architecture

## Objective

Demonstrate an auditable model lifecycle that a reviewer can run without cloud credentials or an
external tracking product. The implementation keeps the domain synthetic so the engineering
controls—not questionable data claims—remain the focus.

## Component flow

```text
Synthetic generator
  -> strict Pydantic records
  -> deterministic stratified train/calibration/test split
  -> StandardScaler + {logistic regression | compact MLP}
  -> disjoint sigmoid calibration + F2 threshold + abstention band
  -> locked-test metrics and subgroup gates
  -> canonical JSON + SHA-256 content-addressed artifact
  -> transactional SQLite registry
  -> champion / challenger deployment snapshot
  -> FastAPI inference
  -> prediction audit + PSI drift evidence
  -> promotion or rollback transaction
```

## Responsibilities

| Component | Responsibility | Trust boundary |
|---|---|---|
| `schemas.py` | Reject unexpected fields and out-of-range values | external input |
| `data.py` | Generate, split, hash, and describe synthetic records | training data |
| `training.py` | Fit candidates and serialize numeric parameters | model building |
| `evaluation.py` | Metrics, calibration error, gates, subgroups, histograms | evidence |
| `artifacts.py` | Validate path, digest, document shape, and numeric safety | artifact load |
| `registry.py` | Atomic lifecycle mutations and immutable history | state change |
| `service.py` | Stable routing, verified model load, prediction logging | inference |
| `drift.py` | Compare current input distributions with training reference | monitoring |
| `api.py` / `cli.py` | Bounded operator and HTTP interfaces | user/operator input |

## Data and control planes

The data plane validates a request, obtains one consistent deployment snapshot, loads only verified
artifacts, makes the champion and optional challenger predictions, serves the deterministically
routed model, and stores no raw feature vector. The control plane registers immutable candidates,
promotes one champion in a transaction, assigns a bounded challenger, and can restore the prior
champion from append-only history.

## Deployment model

The local implementation uses SQLite for a transparent, zero-service demonstration. It assumes a
single writer/API replica. The PostgreSQL DDL preserves the principal constraints for a multi-host
adaptation, but application-level repository support is deliberately out of scope. Artifact
storage is a local directory; production would use immutable object storage, signed provenance,
managed identity, encryption, retention policies, and centralized observability.

## Failure behavior

- No champion: liveness succeeds, readiness and prediction return 503.
- Missing, tampered, malformed, non-finite, or path-escaping artifact: inference fails closed.
- Unknown promotion/challenger: no state change; API maps to 404.
- Challenger equal to champion or invalid traffic percentage: transaction rejects the request.
- No previous champion: rollback fails without mutating deployment state.
- Excessive drift: the report becomes warning/critical; it does not auto-promote or auto-rollback.

The design decision is recorded in
[ADR 0001](adr/0001-portable-artifacts-and-small-registry.md).

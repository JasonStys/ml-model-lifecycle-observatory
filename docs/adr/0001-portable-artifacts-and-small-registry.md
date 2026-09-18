# ADR 0001: Portable artifacts and a small auditable registry

## Status

Accepted — 2026-09-17

## Context

This repository must show the complete lifecycle locally, make every state transition reviewable,
avoid unsafe deserialization, and stay understandable in an interview-sized codebase. It also
needs a path toward production services without pretending the demonstration is one.

## Options considered

| Option | Advantages | Disadvantages |
|---|---|---|
| MLflow plus pickle/joblib | Rich UI and familiar ecosystem | Larger operational surface; executable artifacts inherit dependency and deserialization risk |
| ONNX or `skops.io` plus hosted registry | Stronger ecosystem portability/safety options | Extra runtime/tool complexity obscures the small implemented algorithms |
| Pure JSON numeric artifact plus SQLite registry | Inspectable, deterministic, no executable payload, easy local audit | Supports only explicitly implemented estimators; SQLite is single-writer oriented |

## Decision

Use versioned canonical JSON documents containing feature order, scaling parameters, estimator
weights, calibration parameters, decision thresholds, abstention band, reference histograms, and
provenance. Address artifacts by SHA-256 and validate digest, resolved path, shape, schema, and
finite numbers before inference. Use a purpose-built SQLite registry with transaction-protected
model states, active roles, deployment history, audit events, and prediction events. Include a
constraint-equivalent PostgreSQL schema for integration validation.

## Consequences

Reviewers can inspect an artifact with ordinary tools and the serving runtime needs only NumPy.
The supported algorithm set is intentionally narrow: adding a new estimator requires an explicit
schema/runtime implementation and migration. Horizontal write scaling is not claimed. A real
deployment should move the registry and artifact store behind managed, authenticated services.

## Validation

Tests cover deterministic serialization, idempotent writes, tamper detection, traversal rejection,
malformed dimensions, non-finite values, concurrent registration, transactional promotion,
deterministic routing, and rollback. CI separately loads the PostgreSQL DDL and exercises a key
constraint.

# Operations and rollback runbook

## Deployment assumptions

The included SQLite registry is a single-writer demonstration. Run one API replica, one writable
data volume, a non-root process, and a separately managed admin token. Use the PostgreSQL design
and immutable object storage before horizontal production scaling.

## Startup

1. Run `python -m ml_observatory demo --workspace /data/bootstrap --count 1200` in a controlled
   build or initialization job.
2. Set `OBSERVATORY_REGISTRY_PATH`, `OBSERVATORY_ARTIFACT_ROOT`, and
   `OBSERVATORY_ADMIN_TOKEN` without placing the token in source control.
3. Start `uvicorn ml_observatory.api:app --host 0.0.0.0 --port 8000`.
4. Wait for `/health/live`, then require `/health/ready` before accepting traffic.
5. Confirm `/v1/models` shows the expected model identity and digest.

The Kubernetes example separates startup, liveness, and readiness probes. Readiness depends on a
champion; liveness intentionally does not, so a missing model does not create a restart loop.

## Routine checks

- Compare model/dataset digests with the release record.
- Review prediction volume, response errors, p95 service latency, abstention rate, and outcome
  metrics when labels become available.
- Produce PSI evidence on a representative window; investigate warning/critical inputs rather than
  treating thresholds as proof of model failure.
- Review challenger deltas and subgroup recall before promotion.
- Preserve registry, audit, evaluation, and drift evidence under the defined retention policy.

## Promotion

```bash
python -m ml_observatory promote mdl-0123456789abcdef \
  --registry /data/registry.sqlite3 --reason change-123-reviewed
```

The HTTP equivalent is `POST /v1/admin/models/{model_id}/promote` with `X-Admin-Token`. Record the
reviewer, evidence location, release identifier, and approved rollback target outside the demo
registry if formal change management is required.

## Rollback

Trigger rollback for corrupted release evidence, significant online regression, unsafe subgroup
behavior, material latency/error regression, or a confirmed monitoring/contract failure.

```bash
python -m ml_observatory rollback \
  --registry /data/registry.sqlite3 --reason incident-456
```

Then verify readiness, inspect the champion, send a known-safe contract request, confirm the new
audit event, and continue monitoring. Rollback restores the previous model; it does not undo
upstream data or schema changes.

## Incident triage

| Symptom | First checks | Safe action |
|---|---|---|
| Readiness 503 | champion record, artifact path, digest, volume mount | restore artifact or promote reviewed candidate |
| Prediction 422 | request contract and timestamp/category bounds | fix caller; do not weaken validation |
| Prediction 503 | registry snapshot and artifact validation error | stop rollout, inspect/tamper-check artifact |
| Drift critical | sample size, upstream units, missingness, segment shifts | pause promotion and investigate source |
| Latency budget failure | host contention, model/artifact cache, dependency changes | restore known release; profile offline |
| Admin 401 | token configuration/rotation | repair secret delivery; never log token |

## Backup and recovery

Pause writes, copy the SQLite database using its backup API or a consistent volume snapshot, and
back up the immutable artifact tree plus release metadata. Test restoration to a separate path.
Production PostgreSQL needs managed point-in-time recovery, tested retention, and access controls.

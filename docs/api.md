# API contract

The FastAPI service exposes OpenAPI at `/docs` and `/openapi.json`. All JSON models reject unknown
fields. State-changing endpoints require `X-Admin-Token`, compared in constant time. Use HTTPS and
managed identity in a real deployment.

| Method | Path | Purpose | Key responses |
|---|---|---|---|
| GET | `/health/live` | Process liveness only | 200 |
| GET | `/health/ready` | Verified champion availability | 200, 503 |
| POST | `/v1/predict` | Provenance-rich champion/canary prediction | 200, 422, 503 |
| GET | `/v1/models` | List model metadata and locked-test evidence | 200 |
| POST | `/v1/admin/models/{id}/promote` | Transactionally promote candidate | 200, 401, 404 |
| POST | `/v1/admin/challenger` | Assign shadow/canary at 0–50% | 200, 401, 404, 409 |
| POST | `/v1/admin/rollback` | Restore prior champion | 200, 401, 409 |

## Prediction request

See [the complete example](../examples/predict-request.json). `request_id` is a caller-provided,
non-secret routing key. `observation` follows the [data contract](data-contract.md).

## Prediction response

```json
{
  "request_id": "example-request-0001",
  "model_id": "mdl-0123456789abcdef",
  "model_sha256": "64-character digest",
  "failure_probability": 0.42,
  "decision": "abstain",
  "threshold": 0.39,
  "abstention_band": [0.34, 0.44],
  "challenger_model_id": "mdl-fedcba9876543210",
  "challenger_probability": 0.37
}
```

`decision` is `likely-stable`, `likely-failure`, or `abstain`. Challenger output is evidence; it
is never silently substituted for the model selected by deterministic canary routing.

## Administrative requests

Promotion and rollback accept `{"reason":"reviewed change identifier"}`. Challenger assignment
accepts `{"model_id":"mdl-...","traffic_percent":10}`; zero performs shadow evaluation while a
positive value sends a stable subset of request IDs to the challenger.

The demo token is intentionally simple. Rate limiting, identity federation, tenant isolation,
network policy, and distributed tracing are explicit production follow-ups.

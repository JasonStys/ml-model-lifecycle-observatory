# Data contract

## Dataset

`service-health-v1` contains seeded, synthetic operational observations. Each labeled record has a
stable `row_id`, `service_id`, timezone-aware `observed_at`, eight numeric model features, two
synthetic evaluation segments, and binary `service_failure_24h`. Online requests omit the row ID
and label.

| Field | Type and bounds | Model input |
|---|---|---|
| `request_rate` | float, 0–1,000,000 | yes |
| `p95_latency_ms` | float, 0–120,000 | yes |
| `error_rate` | float, 0–1 | yes |
| `cpu_percent` | float, 0–100 | yes |
| `memory_percent` | float, 0–100 | yes |
| `deploy_age_hours` | float, 0–87,600 | yes |
| `change_failure_rate` | float, 0–1 | yes |
| `saturation_events_15m` | integer, 0–10,000 | yes |
| `region` | `americas`, `emea`, or `apac` | evaluation only |
| `service_tier` | `critical`, `standard`, or `batch` | evaluation only |

`service_id` must match `svc-...`; timestamps must contain an offset and are normalized to UTC.
Unknown fields, NaN/infinity, malformed categories, and out-of-range values are rejected.

## Reproducibility and provenance

Generation uses a local pseudo-random generator with a documented seed and fixed base timestamp.
JSON Lines bytes are canonicalized and hashed. The split is deterministic and stratified into 60%
training, 20% calibration, and 20% locked test partitions. Calibration examples select sigmoid
parameters, the decision threshold, and abstention band. Test examples are used once for the
reported model evidence and promotion gates.

## Privacy and retention

The generator contains no people or external source records. Prediction-event storage deliberately
excludes observations and segment values. A real adaptation must define lawful collection,
minimization, access, deletion, aggregation, and incident procedures before ingesting telemetry.

## Known limitations

Authored equations create the labels, so results do not establish real-world predictive value.
Segments are operational categories—not demographic fairness claims. Time-based leakage analysis,
label delay, concept drift, missingness, and production feedback quality require domain-specific
work before deployment.

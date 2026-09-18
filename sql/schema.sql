-- File: schema.sql
-- Purpose: Define the transactional SQLite model registry, deployment history, audit, and prediction log.
-- Tables and line locations: see docs/code-index.md; partial indexes enforce one active role per deployment.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS models (
    model_id TEXT PRIMARY KEY,
    artifact_sha256 TEXT NOT NULL UNIQUE CHECK (length(artifact_sha256) = 64),
    algorithm TEXT NOT NULL,
    dataset_sha256 TEXT NOT NULL CHECK (length(dataset_sha256) = 64),
    status TEXT NOT NULL CHECK (status IN ('candidate', 'champion', 'retired')),
    metrics_json TEXT NOT NULL,
    artifact_path TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS active_deployments (
    role TEXT PRIMARY KEY CHECK (role IN ('champion', 'challenger')),
    model_id TEXT NOT NULL REFERENCES models(model_id),
    traffic_percent INTEGER NOT NULL CHECK (traffic_percent BETWEEN 0 AND 100),
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS deployment_history (
    deployment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_model_id TEXT REFERENCES models(model_id),
    to_model_id TEXT NOT NULL REFERENCES models(model_id),
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    model_id TEXT REFERENCES models(model_id),
    details_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prediction_events (
    request_id TEXT PRIMARY KEY,
    served_model_id TEXT NOT NULL REFERENCES models(model_id),
    champion_probability REAL NOT NULL CHECK (champion_probability BETWEEN 0.0 AND 1.0),
    challenger_probability REAL CHECK (challenger_probability BETWEEN 0.0 AND 1.0),
    decision TEXT NOT NULL CHECK (decision IN ('likely-stable', 'likely-failure', 'abstain')),
    latency_ms REAL NOT NULL CHECK (latency_ms >= 0.0),
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_models_status_created
    ON models (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_history_to_created
    ON deployment_history (to_model_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_prediction_model_created
    ON prediction_events (served_model_id, created_at DESC);


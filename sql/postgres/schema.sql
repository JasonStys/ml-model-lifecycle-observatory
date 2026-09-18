-- File: schema.sql
-- Purpose: Verify that registry constraints and operational indexes have a PostgreSQL production analogue.
-- Tables and line locations: see docs/code-index.md; JSONB keeps metrics and audit details queryable.
CREATE TABLE IF NOT EXISTS models (
    model_id TEXT PRIMARY KEY,
    artifact_sha256 CHAR(64) NOT NULL UNIQUE,
    algorithm TEXT NOT NULL,
    dataset_sha256 CHAR(64) NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('candidate', 'champion', 'retired')),
    metrics_json JSONB NOT NULL,
    artifact_path TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS active_deployments (
    role TEXT PRIMARY KEY CHECK (role IN ('champion', 'challenger')),
    model_id TEXT NOT NULL REFERENCES models(model_id),
    traffic_percent SMALLINT NOT NULL CHECK (traffic_percent BETWEEN 0 AND 100),
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS deployment_history (
    deployment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    from_model_id TEXT REFERENCES models(model_id),
    to_model_id TEXT NOT NULL REFERENCES models(model_id),
    reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
    audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_type TEXT NOT NULL,
    model_id TEXT REFERENCES models(model_id),
    details_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS prediction_events (
    request_id TEXT PRIMARY KEY,
    served_model_id TEXT NOT NULL REFERENCES models(model_id),
    champion_probability DOUBLE PRECISION NOT NULL
        CHECK (champion_probability BETWEEN 0.0 AND 1.0),
    challenger_probability DOUBLE PRECISION
        CHECK (challenger_probability BETWEEN 0.0 AND 1.0),
    decision TEXT NOT NULL CHECK (decision IN ('likely-stable', 'likely-failure', 'abstain')),
    latency_ms DOUBLE PRECISION NOT NULL CHECK (latency_ms >= 0.0),
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_models_status_created
    ON models (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_history_to_created
    ON deployment_history (to_model_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_prediction_model_created
    ON prediction_events (served_model_id, created_at DESC);


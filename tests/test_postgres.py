"""File: test_postgres.py
Purpose: Verify the PostgreSQL registry schema and its principal integrity constraints.
Symbols and line locations: see docs/code-index.md; the test runs only when CI supplies a DSN.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg")


@pytest.mark.postgres
def test_postgres_schema_constraints_and_indexes() -> None:
    """Production-analogue DDL loads and rejects invalid lifecycle status values."""

    dsn = os.getenv("OBSERVATORY_POSTGRES_DSN")
    if not dsn:
        pytest.skip("OBSERVATORY_POSTGRES_DSN is not configured")
    schema = (Path(__file__).parents[1] / "sql" / "postgres" / "schema.sql").read_text(
        encoding="utf-8"
    )
    with psycopg.connect(dsn) as connection, connection.cursor() as cursor:
        cursor.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
        cursor.execute(schema)
        cursor.execute(
            """
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname = 'public'
            """
        )
        indexes = {row[0] for row in cursor.fetchall()}
        assert "idx_models_status_created" in indexes
        with pytest.raises(psycopg.errors.CheckViolation):
            cursor.execute(
                """
                INSERT INTO models (
                    model_id, artifact_sha256, algorithm, dataset_sha256,
                    status, metrics_json, artifact_path, created_at
                ) VALUES ('bad', %s, 'linear', %s, 'unsafe', '{}', '/tmp/model', now())
                """,
                ("a" * 64, "b" * 64),
            )

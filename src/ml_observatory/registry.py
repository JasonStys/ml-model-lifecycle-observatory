"""File: registry.py
Purpose: Provide transactional model registration, promotion, challenger assignment, rollback,
and audit history.
Symbols and line locations: see docs/code-index.md; Registry is the lifecycle state machine.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ml_observatory.artifacts import ArtifactBundle
from ml_observatory.hashing import canonical_json_bytes

MAX_CHALLENGER_TRAFFIC_PERCENT = 50


@dataclass(frozen=True, slots=True)
class ModelRecord:
    """Registry row used by the service without leaking database details."""

    model_id: str
    artifact_sha256: str
    algorithm: str
    dataset_sha256: str
    status: str
    metrics: dict[str, Any]
    artifact_path: str
    created_at: str


@dataclass(frozen=True, slots=True)
class DeploymentSnapshot:
    """Current champion and optional challenger with deterministic traffic percentage."""

    champion: ModelRecord
    challenger: ModelRecord | None
    challenger_traffic_percent: int


def _utc_now() -> str:
    """Return an RFC 3339 timestamp suitable for lexicographic ordering."""

    return datetime.now(UTC).isoformat()


def _schema_path() -> Path:
    """Locate the SQLite schema in a source checkout or installed wheel."""

    installed = Path(__file__).with_name("sql") / "schema.sql"
    if installed.exists():
        return installed
    return Path(__file__).resolve().parents[2] / "sql" / "schema.sql"


class Registry:
    """SQLite-backed registry with short, explicit write transactions."""

    def __init__(self, path: Path) -> None:
        """Store the registry path; initialization is explicit and idempotent."""

        self.path = path

    def initialize(self) -> None:
        """Create parent storage and apply the idempotent registry schema."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(_schema_path().read_text(encoding="utf-8"))

    def _connect(self) -> sqlite3.Connection:
        """Open a hardened connection with referential integrity and bounded lock waiting."""

        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    @contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
        """Run a write operation under an immediate transaction with automatic rollback."""

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _row_to_model(row: sqlite3.Row) -> ModelRecord:
        """Convert one database row to an immutable application record."""

        return ModelRecord(
            model_id=str(row["model_id"]),
            artifact_sha256=str(row["artifact_sha256"]),
            algorithm=str(row["algorithm"]),
            dataset_sha256=str(row["dataset_sha256"]),
            status=str(row["status"]),
            metrics=json.loads(row["metrics_json"]),
            artifact_path=str(row["artifact_path"]),
            created_at=str(row["created_at"]),
        )

    def register(
        self,
        bundle: ArtifactBundle,
        *,
        algorithm: str,
        dataset_sha256: str,
        metrics: dict[str, Any],
    ) -> ModelRecord:
        """Register a content-addressed candidate idempotently and audit the first insert."""

        model_id = f"mdl-{bundle.artifact_sha256[:16]}"
        created_at = _utc_now()
        metrics_json = canonical_json_bytes(metrics).decode("utf-8")
        with self._write() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO models (
                    model_id, artifact_sha256, algorithm, dataset_sha256,
                    status, metrics_json, artifact_path, created_at
                ) VALUES (?, ?, ?, ?, 'candidate', ?, ?, ?)
                """,
                (
                    model_id,
                    bundle.artifact_sha256,
                    algorithm,
                    dataset_sha256,
                    metrics_json,
                    str(bundle.model_path),
                    created_at,
                ),
            )
            if cursor.rowcount == 1:
                self._audit(
                    connection,
                    "model-registered",
                    model_id,
                    {"artifact_sha256": bundle.artifact_sha256, "algorithm": algorithm},
                    created_at,
                )
            row = connection.execute(
                "SELECT * FROM models WHERE model_id = ?", (model_id,)
            ).fetchone()
        if row is None:
            raise RuntimeError("registered model could not be read")
        record = self._row_to_model(row)
        if (
            record.algorithm != algorithm
            or record.dataset_sha256 != dataset_sha256
            or record.metrics != metrics
        ):
            raise ValueError("content identity is already registered with different metadata")
        return record

    @staticmethod
    def _audit(
        connection: sqlite3.Connection,
        event_type: str,
        model_id: str | None,
        details: dict[str, Any],
        created_at: str,
    ) -> None:
        """Append an immutable audit record inside the caller's transaction."""

        connection.execute(
            """
            INSERT INTO audit_events (event_type, model_id, details_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (event_type, model_id, canonical_json_bytes(details).decode("utf-8"), created_at),
        )

    def get_model(self, model_id: str) -> ModelRecord:
        """Return one model or raise a stable lookup error."""

        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM models WHERE model_id = ?", (model_id,)
            ).fetchone()
        if row is None:
            raise KeyError(model_id)
        return self._row_to_model(row)

    def list_models(self) -> tuple[ModelRecord, ...]:
        """Return models in newest-first order for operational inspection."""

        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM models ORDER BY created_at DESC, model_id"
            ).fetchall()
        return tuple(self._row_to_model(row) for row in rows)

    def promote(self, model_id: str, reason: str = "quality-gates-passed") -> None:
        """Atomically replace the champion and preserve the prior model for rollback."""

        timestamp = _utc_now()
        with self._write() as connection:
            candidate = connection.execute(
                "SELECT model_id FROM models WHERE model_id = ?", (model_id,)
            ).fetchone()
            if candidate is None:
                raise KeyError(model_id)
            current = connection.execute(
                "SELECT model_id FROM active_deployments WHERE role = 'champion'"
            ).fetchone()
            previous = str(current["model_id"]) if current else None
            if previous == model_id:
                return
            if previous is not None:
                connection.execute(
                    "UPDATE models SET status = 'retired' WHERE model_id = ?", (previous,)
                )
            connection.execute(
                "UPDATE models SET status = 'champion' WHERE model_id = ?", (model_id,)
            )
            connection.execute(
                """
                INSERT INTO active_deployments (role, model_id, traffic_percent, updated_at)
                VALUES ('champion', ?, 100, ?)
                ON CONFLICT(role) DO UPDATE SET
                    model_id = excluded.model_id,
                    traffic_percent = excluded.traffic_percent,
                    updated_at = excluded.updated_at
                """,
                (model_id, timestamp),
            )
            # A promotion closes the prior experiment so one model cannot be both
            # champion and challenger and stale canary traffic cannot survive.
            connection.execute("DELETE FROM active_deployments WHERE role = 'challenger'")
            connection.execute(
                """
                INSERT INTO deployment_history (from_model_id, to_model_id, reason, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (previous, model_id, reason, timestamp),
            )
            self._audit(
                connection,
                "champion-promoted",
                model_id,
                {"from_model_id": previous, "reason": reason},
                timestamp,
            )

    def assign_challenger(self, model_id: str, traffic_percent: int = 0) -> None:
        """Activate a challenger for shadow or bounded deterministic canary traffic."""

        if not 0 <= traffic_percent <= MAX_CHALLENGER_TRAFFIC_PERCENT:
            raise ValueError("challenger traffic must be between 0 and 50 percent")
        timestamp = _utc_now()
        with self._write() as connection:
            candidate = connection.execute(
                "SELECT model_id FROM models WHERE model_id = ?", (model_id,)
            ).fetchone()
            champion = connection.execute(
                "SELECT model_id FROM active_deployments WHERE role = 'champion'"
            ).fetchone()
            if candidate is None:
                raise KeyError(model_id)
            if champion is None:
                raise RuntimeError("a champion is required before assigning a challenger")
            if str(champion["model_id"]) == model_id:
                raise ValueError("champion and challenger must be different models")
            connection.execute(
                """
                INSERT INTO active_deployments (role, model_id, traffic_percent, updated_at)
                VALUES ('challenger', ?, ?, ?)
                ON CONFLICT(role) DO UPDATE SET
                    model_id = excluded.model_id,
                    traffic_percent = excluded.traffic_percent,
                    updated_at = excluded.updated_at
                """,
                (model_id, traffic_percent, timestamp),
            )
            self._audit(
                connection,
                "challenger-assigned",
                model_id,
                {"traffic_percent": traffic_percent},
                timestamp,
            )

    def clear_challenger(self) -> None:
        """Remove the active challenger while preserving its registry and audit history."""

        timestamp = _utc_now()
        with self._write() as connection:
            current = connection.execute(
                "SELECT model_id FROM active_deployments WHERE role = 'challenger'"
            ).fetchone()
            connection.execute("DELETE FROM active_deployments WHERE role = 'challenger'")
            if current is not None:
                model_id = str(current["model_id"])
                self._audit(connection, "challenger-cleared", model_id, {}, timestamp)

    def rollback(self, reason: str = "operator-rollback") -> str:
        """Promote the most recent prior champion and return its model identifier."""

        with self._connect() as connection:
            current = connection.execute(
                "SELECT model_id FROM active_deployments WHERE role = 'champion'"
            ).fetchone()
            if current is None:
                raise RuntimeError("no champion is deployed")
            prior = connection.execute(
                """
                SELECT from_model_id
                FROM deployment_history
                WHERE to_model_id = ? AND from_model_id IS NOT NULL
                ORDER BY deployment_id DESC
                LIMIT 1
                """,
                (str(current["model_id"]),),
            ).fetchone()
        if prior is None:
            raise RuntimeError("no prior champion is available")
        model_id = str(prior["from_model_id"])
        self.promote(model_id, reason=reason)
        return model_id

    def deployment_snapshot(self) -> DeploymentSnapshot:
        """Read champion and challenger roles in one consistent query snapshot."""

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT d.role, d.traffic_percent, m.*
                FROM active_deployments AS d
                JOIN models AS m ON m.model_id = d.model_id
                ORDER BY d.role
                """
            ).fetchall()
        deployments = {str(row["role"]): row for row in rows}
        if "champion" not in deployments:
            raise RuntimeError("no champion is deployed")
        champion = self._row_to_model(deployments["champion"])
        challenger_row = deployments.get("challenger")
        challenger = self._row_to_model(challenger_row) if challenger_row is not None else None
        traffic = int(challenger_row["traffic_percent"]) if challenger_row is not None else 0
        return DeploymentSnapshot(champion, challenger, traffic)

    def record_prediction(  # noqa: PLR0913
        self,
        *,
        request_id: str,
        served_model_id: str,
        champion_probability: float,
        challenger_probability: float | None,
        decision: str,
        latency_ms: float,
    ) -> None:
        """Idempotently record prediction provenance without storing raw input features."""

        with self._write() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO prediction_events (
                    request_id, served_model_id, champion_probability,
                    challenger_probability, decision, latency_ms, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    served_model_id,
                    champion_probability,
                    challenger_probability,
                    decision,
                    latency_ms,
                    _utc_now(),
                ),
            )

    def audit_events(self) -> tuple[dict[str, Any], ...]:
        """Return ordered audit events for validation and operator review."""

        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM audit_events ORDER BY audit_id").fetchall()
        return tuple(
            {
                "audit_id": int(row["audit_id"]),
                "event_type": str(row["event_type"]),
                "model_id": row["model_id"],
                "details": json.loads(row["details_json"]),
                "created_at": str(row["created_at"]),
            }
            for row in rows
        )

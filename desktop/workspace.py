"""File: desktop/workspace.py
Purpose: Retain bounded native data and invoke the original verified model-lifecycle contracts.
Symbols and variables: see docs/code-index.md; Workspace owns one local registry and artifact root.
No network, executable model deserialization, automatic promotion or production data is required.
"""

from __future__ import annotations

import json
import math
import os
import secrets
import stat
import sys
from pathlib import Path
from typing import Any

from ml_observatory.artifacts import load_artifact, write_artifact
from ml_observatory.data import dataset_payload, generate_dataset, split_dataset
from ml_observatory.drift import evaluate_drift
from ml_observatory.hashing import sha256_bytes
from ml_observatory.registry import ModelRecord, Registry
from ml_observatory.review import model_review
from ml_observatory.schemas import DatasetRecord, Observation, PredictRequest
from ml_observatory.service import ModelService
from ml_observatory.training import train_candidates

MAX_BYTES = 5 * 1024 * 1024
MAX_RECORDS = 4000
MIN_RECORDS = 400
PRODUCT = "ml-model-lifecycle-observatory"
MIN_CLASS_ROWS = 20
MAX_TRAFFIC = 50
MIN_REASON = 10
MAX_REASON = 300
MAX_OBSERVATION = 32768

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl


def read_regular(path: Path, limit: int = MAX_BYTES) -> bytes:
    """Bound the opened descriptor; reject links, special files, growth and identity swaps."""
    descriptor = os.open(
        path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    )
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        named = path.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or stat.S_ISLNK(named.st_mode)
            or (info.st_dev, info.st_ino) != (named.st_dev, named.st_ino)
            or info.st_size > limit
        ):
            raise ValueError("Choose a bounded regular local file, without links")
        raw = stream.read(limit + 1)
    if len(raw) != info.st_size or len(raw) > limit:
        raise ValueError("Local file changed or exceeded its limit")
    return raw


def strict_json(text: str) -> Any:
    """Reject ambiguous object keys and nonfinite literals before typed schema validation."""

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON field")
            result[key] = value
        return result

    def invalid(_: str) -> None:
        raise ValueError("Nonfinite JSON value")

    def decimal(value: str) -> float:
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("Nonfinite JSON value")
        return result

    return json.loads(text, object_pairs_hook=pairs, parse_constant=invalid, parse_float=decimal)


def parse_dataset(text: str) -> tuple[DatasetRecord, ...]:
    "Accept bounded JSON Lines with unique identities, both labels and usable held-out partitions."
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise ValueError("Dataset exceeds 5 MiB")
    lines = [line for line in text.splitlines() if line.strip()]
    if not MIN_RECORDS <= len(lines) <= MAX_RECORDS:
        raise ValueError("Use 400-4000 labeled JSON Lines records")
    records = tuple(DatasetRecord.model_validate(strict_json(line)) for line in lines)
    if len({record.row_id for record in records}) != len(records):
        raise ValueError("Each dataset row_id must be unique")
    if (
        min(sum(record.service_failure_24h == label for record in records) for label in (0, 1))
        < MIN_CLASS_ROWS
    ):
        raise ValueError("At least 20 rows of each outcome are required")
    split_dataset(records)
    return records


def default_profile() -> Path:
    """Place durable work outside source/install folders under this OS account."""
    if sys.platform == "win32":
        base = Path(os.environ["LOCALAPPDATA"])
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
    if not base.is_absolute():
        raise ValueError("Application-data directory must be absolute")
    return base / "JasonStysPortfolio" / PRODUCT / "workspace"


def profile_directory(directory: Path) -> Path:
    """Refuse linked ancestors and frozen installation/resources before any profile mutation."""
    absolute = directory.absolute()
    for part in (absolute, *absolute.parents):
        if part.is_symlink() or part.is_junction():
            raise ValueError("Linked profile directories are not supported")
    if getattr(sys, "frozen", False):
        installation = Path(sys.executable).resolve().parent
        resources = Path(sys._MEIPASS).resolve()
        destination = absolute.resolve()
        if any(destination.is_relative_to(root) for root in (installation, resources)):
            raise ValueError("Choose durable data outside the installed application/resources")
    return absolute


class Workspace:
    "One trusted OS owner's durable registry; mutations remain explicit original core operations."

    def __init__(self, directory: Path):
        "Identify a new/known profile, lock it before registry work, and never adopt unknown files."
        absolute = profile_directory(directory)
        absolute.mkdir(parents=True, exist_ok=True, mode=0o700)
        marker = absolute / "profile.json"
        entries = tuple(absolute.iterdir())
        identity = {"schema": 1, "product": PRODUCT}
        if not entries:
            with marker.open("x", encoding="utf-8") as stream:
                json.dump(identity, stream, separators=(",", ":"))
                stream.flush()
                os.fsync(stream.fileno())
        if strict_json(read_regular(marker, 1024).decode("utf-8")) != identity:
            raise ValueError("Unknown profile identity; no migration or reset was attempted")
        self.directory = absolute.resolve()
        self.descriptor = os.open(
            absolute / "owner.lock",
            os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
            0o600,
        )
        try:
            info = os.fstat(self.descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError("Profile ownership requires a regular exclusive lock")
            if info.st_size == 0:
                os.write(self.descriptor, b"0")
            os.lseek(self.descriptor, 0, os.SEEK_SET)
            if sys.platform == "win32":
                msvcrt.locking(self.descriptor, msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(self.descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.artifacts = self.directory / "models"
            self.dataset = self.directory / "dataset.jsonl"
            database = self.directory / "registry.sqlite3"
            if database.is_symlink() or self.artifacts.is_symlink() or self.artifacts.is_junction():
                raise ValueError("Linked registry/artifact paths are not supported")
            if database.exists():
                # SQLite stays authoritative; reject aliases before opening its path.
                info = database.stat()
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise ValueError("Registry must be a regular one-link file")
            self.registry = Registry(database)
            self.registry.initialize()
        except BaseException:
            os.close(self.descriptor)
            self.descriptor = -1
            raise

    def close(self) -> None:
        """Release only the retained owner descriptor after UI background work has completed."""
        if self.descriptor >= 0:
            os.close(self.descriptor)
            self.descriptor = -1

    def _open(self) -> None:
        """Reject accidentally invoked operations after native ownership is released."""
        if self.descriptor < 0:
            raise ValueError("Workspace is closed")

    def prepare(self, count: int, seed: int) -> str:
        """Generate editable observations; this never trains, saves or promotes a model."""
        self._open()
        if type(count) is not int or not MIN_RECORDS <= count <= MAX_RECORDS:
            raise ValueError("Prepared record count must be 400-4000")
        if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
            raise ValueError("Seed must be an unsigned 32-bit integer")
        return dataset_payload(generate_dataset(count, seed)).decode("utf-8")

    def train(self, text: str, seed: int) -> list[dict[str, Any]]:
        """Persist validated data, train both real candidates and register them without automatic
        promotion."""
        self._open()
        if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
            raise ValueError("Seed must be an unsigned 32-bit integer")
        records = parse_dataset(text)
        payload = dataset_payload(records)
        digest = sha256_bytes(payload)
        temporary = self.directory / ("dataset-" + secrets.token_hex(16) + ".tmp")
        try:
            with temporary.open("xb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.dataset)
        finally:
            temporary.unlink(missing_ok=True)
        result = []
        for candidate in train_candidates(split_dataset(records, seed), digest, seed=seed):
            bundle = write_artifact(self.artifacts, candidate.document)
            record = self.registry.register(
                bundle,
                algorithm=candidate.algorithm,
                dataset_sha256=digest,
                metrics=candidate.metrics,
            )
            result.append(self._summary(record))
        return result

    @staticmethod
    def _summary(record: ModelRecord) -> dict[str, Any]:
        """Expose useful registry evidence without leaking OS profile paths into local exports."""
        return {
            "model_id": record.model_id,
            "artifact_sha256": record.artifact_sha256,
            "dataset_sha256": record.dataset_sha256,
            "algorithm": record.algorithm,
            "status": record.status,
            "metrics": record.metrics,
            "created_at": record.created_at,
        }

    def models(self) -> list[dict[str, Any]]:
        """Return actual registered records and status, without fabricating deployment state."""
        self._open()
        return [self._summary(record) for record in self.registry.list_models()]

    def review(self, model_id: str) -> dict[str, Any]:
        """Build the original hash-verified dossier; recorded evaluation is explicitly not rerun."""
        self._open()
        return model_review(self.registry, self.artifacts, model_id)

    def promote(self, model_id: str, reason: str) -> dict[str, Any]:
        """Reverify bundle and gates immediately before explicit audited promotion."""
        self._open()
        dossier = self.review(model_id)
        if not all(dossier["quality_gates"].values()):
            raise ValueError("Recorded quality gates failed; this native action cannot promote it")
        self._reason(reason)
        self.registry.promote(model_id, reason=reason.strip())
        return self.review(model_id)

    def challenger(self, model_id: str, traffic: int) -> dict[str, Any]:
        """Verify the candidate before original shadow/canary assignment.

        The returned dossier is actual registry state, not a deployment simulation.
        """
        self._open()
        self.review(model_id)
        if type(traffic) is not int or not 0 <= traffic <= MAX_TRAFFIC:
            raise ValueError("Challenger traffic must be 0-50 percent; 0 means shadow only")
        self.registry.assign_challenger(model_id, traffic)
        return self.review(model_id)

    @staticmethod
    def _reason(reason: str) -> None:
        """Require a useful bounded explicit reason rather than an automatic lifecycle decision."""
        if not isinstance(reason, str) or not MIN_REASON <= len(reason.strip()) <= MAX_REASON:
            raise ValueError("Enter a review reason of 10-300 characters")

    def rollback(self, reason: str) -> str:
        """Reverify the prior bundle and recorded gates before original audited rollback."""
        self._open()
        self._reason(reason)
        current = self.registry.deployment_snapshot().champion.model_id
        dossier = self.review(current)
        prior = dossier["rollback_context"]["prior_candidate"]
        if prior is None:
            raise RuntimeError("No prior champion is recorded for rollback")
        if not self.review(prior)["eligible_on_recorded_quality"]:
            raise ValueError("Prior model's recorded quality gates require further review")
        return self.registry.rollback(reason=reason.strip())

    def predict(self, text: str) -> dict[str, Any]:
        """Predict one validated observation using real champion/canary routing."""
        self._open()
        if len(text.encode("utf-8")) > MAX_OBSERVATION:
            raise ValueError("Observation exceeds 32 KiB")
        observation = Observation.model_validate(strict_json(text))
        request = PredictRequest(request_id=secrets.token_hex(16), observation=observation)
        return ModelService(self.registry, self.artifacts).predict(request).model_dump(mode="json")

    def drift(self, model_id: str, text: str) -> dict[str, Any]:
        """Compute actual PSI for current validated observations; it never changes a deployment."""
        self._open()
        self.review(model_id)
        record = self.registry.get_model(model_id)
        model = load_artifact(self.artifacts, record.artifact_sha256)
        return evaluate_drift(model, parse_dataset(text)).model_dump(mode="json")


def export_new(path: Path, value: Any) -> None:
    """Export user-chosen evidence exclusively, refusing all existing destinations without a
    precheck."""
    payload = json.dumps(value, indent=2, sort_keys=True, allow_nan=False).encode("utf-8") + b"\n"
    if len(payload) > MAX_BYTES:
        raise ValueError("Evidence exceeds the export budget")
    with path.open("xb") as output:
        output.write(payload)
        output.flush()
        os.fsync(output.fileno())

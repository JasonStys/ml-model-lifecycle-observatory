"""File: cli.py
Purpose: Provide deterministic demo, benchmark, registry, deployment, rollback, and API commands.
Symbols and line locations: see docs/code-index.md; build_parser documents the supported
operator surface.
"""

from __future__ import annotations

import argparse
import json
import statistics
import tempfile
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import uvicorn

from ml_observatory.artifacts import load_artifact, write_artifact
from ml_observatory.data import dataset_payload, generate_dataset, split_dataset
from ml_observatory.hashing import sha256_bytes
from ml_observatory.lifecycle import run_demo
from ml_observatory.registry import Registry
from ml_observatory.reports import write_json
from ml_observatory.training import select_candidate, train_candidates

MIN_BENCHMARK_RECORDS = 400
MAX_TRAINING_SECONDS = 30.0
MAX_P95_INFERENCE_MS = 5.0


def _path(value: str) -> Path:
    """Convert a CLI path to an absolute path without requiring it to exist."""

    return Path(value).expanduser().resolve()


def build_parser() -> argparse.ArgumentParser:
    """Build the documented command tree and bounded input validation."""

    parser = argparse.ArgumentParser(prog="ml-observatory")
    commands = parser.add_subparsers(dest="command", required=True)

    demo = commands.add_parser("demo", help="run the complete synthetic lifecycle")
    demo.add_argument("--workspace", type=_path, default=_path(".artifacts/demo"))
    demo.add_argument("--count", type=int, default=1_200)
    demo.add_argument("--seed", type=int, default=20260917)

    benchmark = commands.add_parser("benchmark", help="enforce training and inference budgets")
    benchmark.add_argument("--report", type=_path)
    benchmark.add_argument("--count", type=int, default=800)

    inspect = commands.add_parser("inspect", help="print registry state")
    inspect.add_argument("--registry", type=_path, required=True)

    promote = commands.add_parser("promote", help="promote a registered model")
    promote.add_argument("model_id")
    promote.add_argument("--registry", type=_path, required=True)
    promote.add_argument("--reason", default="operator-approved")

    challenger = commands.add_parser("challenger", help="assign a shadow or canary challenger")
    challenger.add_argument("model_id")
    challenger.add_argument("--registry", type=_path, required=True)
    challenger.add_argument("--traffic-percent", type=int, default=0)

    rollback = commands.add_parser("rollback", help="restore the prior champion")
    rollback.add_argument("--registry", type=_path, required=True)
    rollback.add_argument("--reason", default="operator-rollback")

    serve = commands.add_parser("serve", help="run the FastAPI service")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    return parser


def run_benchmark(report_path: Path | None, count: int = 800) -> dict[str, Any]:
    """Measure deterministic training and portable inference against conservative budgets."""

    if count < MIN_BENCHMARK_RECORDS:
        raise ValueError("benchmark count must be at least 400")
    records = generate_dataset(count=count)
    dataset_sha256 = sha256_bytes(dataset_payload(records))
    splits = split_dataset(records)
    training_started = time.perf_counter()
    selected = select_candidate(train_candidates(splits, dataset_sha256))
    training_seconds = time.perf_counter() - training_started
    with tempfile.TemporaryDirectory(prefix="ml-observatory-benchmark-") as directory:
        root = Path(directory)
        bundle = write_artifact(root, selected.document)
        model = load_artifact(root, bundle.artifact_sha256)
        samples = tuple(splits.test[: min(100, len(splits.test))])
        latencies: list[float] = []
        inference_started = time.perf_counter()
        for index in range(5_000):
            started = time.perf_counter()
            model.predict_probability(samples[index % len(samples)])
            latencies.append((time.perf_counter() - started) * 1_000.0)
        inference_seconds = time.perf_counter() - inference_started
    sorted_latencies = sorted(latencies)
    p95_latency_ms = sorted_latencies[int(len(sorted_latencies) * 0.95)]
    report = {
        "schema_version": 1,
        "training_records": count,
        "training_seconds": training_seconds,
        "inference_requests": len(latencies),
        "inference_seconds": inference_seconds,
        "inference_per_second": len(latencies) / inference_seconds,
        "mean_inference_ms": statistics.fmean(latencies),
        "p95_inference_ms": p95_latency_ms,
        "budgets": {
            "training_seconds_max": MAX_TRAINING_SECONDS,
            "p95_inference_ms_max": MAX_P95_INFERENCE_MS,
        },
        "passed": (
            training_seconds <= MAX_TRAINING_SECONDS and p95_latency_ms <= MAX_P95_INFERENCE_MS
        ),
    }
    if report_path is not None:
        write_json(report_path, report)
    if not report["passed"]:
        raise RuntimeError(f"performance budget failed: {report}")
    return report


def main(argv: list[str] | None = None) -> int:  # noqa: PLR0911
    """Execute one operator command and emit machine-readable summaries."""

    arguments = build_parser().parse_args(argv)
    if arguments.command == "demo":
        result = run_demo(arguments.workspace, count=arguments.count, seed=arguments.seed)
        print(json.dumps(asdict(result), default=str, indent=2, sort_keys=True))
        return 0
    if arguments.command == "benchmark":
        print(json.dumps(run_benchmark(arguments.report, count=arguments.count), indent=2))
        return 0
    if arguments.command == "serve":
        uvicorn.run("ml_observatory.api:app", host=arguments.host, port=arguments.port)
        return 0
    registry = Registry(arguments.registry)
    registry.initialize()
    if arguments.command == "inspect":
        print(
            json.dumps(
                {
                    "models": [asdict(model) for model in registry.list_models()],
                    "audit_events": registry.audit_events(),
                },
                default=str,
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if arguments.command == "promote":
        registry.promote(arguments.model_id, reason=arguments.reason)
        print(json.dumps({"status": "promoted", "model_id": arguments.model_id}))
        return 0
    if arguments.command == "challenger":
        registry.assign_challenger(arguments.model_id, arguments.traffic_percent)
        print(json.dumps({"status": "challenger-assigned", "model_id": arguments.model_id}))
        return 0
    if arguments.command == "rollback":
        model_id = registry.rollback(reason=arguments.reason)
        print(json.dumps({"status": "rolled-back", "model_id": model_id}))
        return 0
    raise AssertionError(f"unhandled command: {arguments.command}")


if __name__ == "__main__":
    raise SystemExit(main())

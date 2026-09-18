"""File: test_cli.py
Purpose: Verify command parsing, benchmark budgets, registry inspection, and
delegated server startup.
Symbols and line locations: see docs/code-index.md; tests cover every public command branch.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ml_observatory import cli
from ml_observatory.lifecycle import DemoResult
from ml_observatory.registry import Registry


def test_benchmark_meets_training_and_inference_budgets(tmp_path: Path) -> None:
    """The actual linear/neural training and portable runtime remain under generous CI budgets."""

    report_path = tmp_path / "benchmark.json"
    report = cli.run_benchmark(report_path, count=800)
    assert report["passed"] is True
    assert report["inference_requests"] == 5_000
    assert json.loads(report_path.read_text(encoding="utf-8"))["passed"] is True
    with pytest.raises(ValueError, match="at least 400"):
        cli.run_benchmark(None, count=399)


def test_demo_and_benchmark_command_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """CLI commands emit parseable summaries and forward documented arguments."""

    result = DemoResult(
        registry_path=tmp_path / "registry.sqlite3",
        dataset_path=tmp_path / "dataset.jsonl",
        champion_model_id="mdl-0000000000000001",
        champion_sha256="a" * 64,
        challenger_model_id="mdl-0000000000000002",
        drift_level="critical",
    )
    monkeypatch.setattr(
        cli,
        "run_demo",
        lambda _workspace, **_kwargs: result,
    )
    assert cli.main(["demo", "--workspace", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["drift_level"] == "critical"
    monkeypatch.setattr(
        cli,
        "run_benchmark",
        lambda _report, **_kwargs: {"passed": True},
    )
    assert cli.main(["benchmark", "--count", "800"]) == 0
    assert json.loads(capsys.readouterr().out)["passed"] is True


def test_registry_commands_cover_inspect_promote_challenger_and_rollback(
    deployed_registry: tuple[Registry, str, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Operator commands execute lifecycle mutations against an explicit registry path."""

    registry, champion_id, challenger_id = deployed_registry
    assert cli.main(["inspect", "--registry", str(registry.path)]) == 0
    assert len(json.loads(capsys.readouterr().out)["models"]) == 2
    assert (
        cli.main(
            [
                "promote",
                challenger_id,
                "--registry",
                str(registry.path),
                "--reason",
                "test-promotion",
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert (
        cli.main(
            [
                "challenger",
                champion_id,
                "--registry",
                str(registry.path),
                "--traffic-percent",
                "5",
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert cli.main(["rollback", "--registry", str(registry.path)]) == 0
    assert json.loads(capsys.readouterr().out)["model_id"] == champion_id


def test_serve_command_delegates_to_uvicorn(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve command forwards a bounded host and port without starting a process in tests."""

    calls: list[tuple[str, str, int]] = []
    monkeypatch.setattr(
        cli.uvicorn,
        "run",
        lambda application, host, port: calls.append((application, host, port)),
    )
    assert cli.main(["serve", "--host", "127.0.0.1", "--port", "9000"]) == 0
    assert calls == [("ml_observatory.api:app", "127.0.0.1", 9000)]


def test_parser_requires_a_command() -> None:
    """Calling the CLI without an operation returns argparse's usage error."""

    with pytest.raises(SystemExit):
        cli.build_parser().parse_args([])

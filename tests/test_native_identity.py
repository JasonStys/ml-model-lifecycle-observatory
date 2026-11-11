"""File: test_native_identity.py
Purpose: Reject stale/tampered frozen metadata and unauthorized synthetic-profile selection.
Symbols: frozen_identity fixture uses only a temporary SOURCE document, never an OS profile.
"""

import json
import platform
import sys
from pathlib import Path

import pytest

from desktop import launcher
from desktop.workspace import PRODUCT
from ml_observatory import VERSION


@pytest.fixture
def frozen_identity(tmp_path: Path, monkeypatch) -> tuple[Path, dict]:
    """Model the actual embedded identity format with a bounded regular file."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    identity = {
        "schema": 1,
        "product": PRODUCT,
        "version": VERSION,
        "source": "a" * 40,
        "sourceDirty": False,
        "python": platform.python_version(),
        "tcl": "9.0.4",
        "tk": "9.0.4",
    }
    path = tmp_path / "SOURCE.json"
    path.write_text(json.dumps(identity), encoding="utf-8")
    return path, identity


def test_embedded_identity_requires_actual_product_runtime_and_strict_shape(
    frozen_identity,
) -> None:
    """A genuine coherent record is accepted; each changed identity field is rejected."""
    path, identity = frozen_identity
    assert launcher.package_identity() == identity
    changes = [
        ("schema", True),
        ("product", "other-product"),
        ("version", "1.0.0"),
        ("source", "a" * 39),
        ("sourceDirty", "false"),
        ("python", "3.12.10"),
        ("tcl", 9),
        ("tk", None),
        ("unexpected", "not accepted"),
    ]
    for key, value in changes:
        path.write_text(json.dumps({**identity, key: value}), encoding="utf-8")
        with pytest.raises(ValueError):
            launcher.package_identity()
    path.write_text('{"schema":1,"schema":1}', encoding="utf-8")
    with pytest.raises(ValueError):
        launcher.package_identity()


def test_marked_acceptance_never_selects_or_reuses_an_unidentified_profile(tmp_path: Path) -> None:
    """Only the byte-exact marked first/reopen modes may enter the native test harness."""
    marker = tmp_path / "acceptance.marker"
    marker.write_bytes(b"ml-observatory-owned-native-acceptance-v1\r\n")
    with pytest.raises(ValueError):
        launcher.parse_arguments(["--native-acceptance-root", str(tmp_path)])
    marker.write_bytes(b"ml-observatory-owned-native-acceptance-v1\n")
    result = launcher.parse_arguments(["--native-acceptance-root", str(tmp_path)])
    assert result.native_acceptance_root == tmp_path and not result.acceptance_reopen
    (tmp_path / "profile").mkdir()
    with pytest.raises(ValueError):
        launcher.parse_arguments(["--native-acceptance-root", str(tmp_path)])
    result = launcher.parse_arguments(
        ["--native-acceptance-root", str(tmp_path), "--acceptance-reopen"]
    )
    assert result.acceptance_reopen
    for option in (["--profile", str(tmp_path)], ["--runtime-info"]):
        with pytest.raises(SystemExit):
            launcher.parse_arguments(["--native-acceptance-root", str(tmp_path), *option])


def test_runtime_record_refuses_existing_output_without_opening_a_workspace(tmp_path: Path) -> None:
    """A windowed binary can expose runtime identity through an exclusive new output file."""
    output = tmp_path / "runtime.json"
    arguments = launcher.parse_arguments(["--runtime-info", "--runtime-info-output", str(output)])
    launcher.emit_runtime_info(arguments, {"version": VERSION}, {"python": "observed"})
    original = output.read_bytes()
    assert json.loads(original)["package"]["version"] == VERSION
    with pytest.raises(FileExistsError):
        launcher.emit_runtime_info(arguments, {}, {})
    assert output.read_bytes() == original

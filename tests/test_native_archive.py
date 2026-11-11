"""File: test_native_archive.py
Purpose: Validate real Windows archive boundaries with independent malicious/collision fixtures.
Symbols: archive/extract paths are owned temporary directories; no executable is launched here.
"""

import stat
import zipfile
from pathlib import Path

import pytest

from scripts import archive_native


def test_regular_portable_payload_round_trip_and_no_overwrite(tmp_path: Path) -> None:
    """Actual nested bytes survive relocation; previous archive/destination is never replaced."""
    bundle = tmp_path / "bundle"
    (bundle / "nested").mkdir(parents=True)
    (bundle / "nested/content.txt").write_bytes(b"actual synthetic bytes\x00\xff")
    archive = tmp_path / "new.zip"
    assert len(archive_native.create_archive(bundle, archive)) == 64
    target = tmp_path / "target"
    archive_native.extract_archive(archive, target)
    assert (target / "nested/content.txt").read_bytes() == b"actual synthetic bytes\x00\xff"
    with pytest.raises(FileExistsError):
        archive_native.create_archive(bundle, archive)
    with pytest.raises(FileExistsError):
        archive_native.extract_archive(archive, target)


@pytest.mark.parametrize(
    "name",
    [
        "../escape",
        "/absolute",
        "C:/drive",
        "a\\escape",
        "a:stream",
        "NUL",
        "path/CON.txt",
        "trailing.",
        "space ",
    ],
)
def test_unsafe_names_fail_before_destination_creation(tmp_path: Path, name: str) -> None:
    """Traversal, Windows devices/streams and ambiguous names cannot become extracted output."""
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr(name, b"not extracted")
    if "\\" in name:
        # Windows ZipFile normalizes its writer's convenience path; patch real local/central names.
        raw = archive.read_bytes().replace(name.replace("\\", "/").encode(), name.encode())
        archive.write_bytes(raw)
        with zipfile.ZipFile(archive) as package:
            assert "\\" in package.infolist()[0].orig_filename
    target = tmp_path / "target"
    with pytest.raises(ValueError):
        archive_native.extract_archive(archive, target)
    assert not target.exists() and not (tmp_path / "escape").exists()


def test_case_aliases_and_declared_special_files_are_rejected(tmp_path: Path) -> None:
    """Distinct ZIP spellings cannot collide on Windows; declared links/devices are refused."""
    archive = tmp_path / "case.zip"
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr("Case.txt", b"first")
        package.writestr("case.TXT", b"second")
    with pytest.raises(ValueError):
        archive_native.extract_archive(archive, tmp_path / "case-output")
    for index, mode in enumerate((stat.S_IFLNK, stat.S_IFCHR)):
        archive = tmp_path / f"special-{index}.zip"
        info = zipfile.ZipInfo("special")
        info.create_system = 3
        info.external_attr = (mode | 0o600) << 16
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr(info, b"target")
        with pytest.raises(ValueError):
            archive_native.extract_archive(archive, tmp_path / f"out-{index}")


def test_real_expansion_budget_is_checked_before_extraction(tmp_path: Path, monkeypatch) -> None:
    """A genuine compressed file larger than the test budget is refused without creating output."""
    archive = tmp_path / "expanded.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as package:
        package.writestr("data", b"a" * 4096)
    monkeypatch.setattr(archive_native, "MAX_MEMBER", 1024)
    with pytest.raises(ValueError):
        archive_native.extract_archive(archive, tmp_path / "expanded-output")
    assert not (tmp_path / "expanded-output").exists()


def test_small_metadata_is_regular_and_actually_bounded(tmp_path: Path) -> None:
    """Real oversize bytes, arrays and hardlink aliases fail before metadata is trusted."""
    path = tmp_path / "metadata"
    path.write_text('{"schema":1}')
    assert archive_native.read_small_json(path) == {"schema": 1}
    path.write_bytes(b" " * 8193)
    with pytest.raises(ValueError):
        archive_native.read_small_json(path)
    path.write_text("[]")
    with pytest.raises(ValueError):
        archive_native.read_small_json(path)
    (tmp_path / "alias").hardlink_to(path)
    with pytest.raises(ValueError):
        archive_native.read_small_json(path)


def test_native_marker_protocol_is_byte_exact_and_existing_proof_is_not_reused(
    tmp_path: Path,
) -> None:
    """Windows newline translation cannot change the authorization marker into CRLF."""
    root = tmp_path / "proof"
    archive_native.prepare_test_root(root)
    marker = root / "acceptance.marker"
    assert marker.read_bytes() == b"ml-observatory-owned-native-acceptance-v1\n"
    with pytest.raises(FileExistsError):
        archive_native.prepare_test_root(root)

"""File: scripts/archive_native.py
Purpose: Relocate a bounded complete Windows ZIP and exercise its actual native application twice.
Symbols: create_archive/extract_archive guard payloads.
run_application owns only marked test children.
State: fresh project release/proof directories, exact package metadata and synthetic receipts only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
MAX_MEMBERS = 5000
MAX_TOTAL = 2 * 1024 * 1024 * 1024
MAX_MEMBER = 256 * 1024 * 1024
BLOCK = 65536
EXECUTABLE = "MLModelLifecycleObservatory.exe"
RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def create_archive(bundle: Path, archive: Path) -> str:
    """Write a bounded regular payload to a fresh archive without replacement."""
    files = sorted(bundle.rglob("*"))
    if not files or len(files) > MAX_MEMBERS:
        raise ValueError("Portable member inventory is empty or exceeds its bound")
    total = 0
    for path in files:
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or not (path.is_dir() or stat.S_ISREG(info.st_mode)):
            raise ValueError("Portable input contains a link or special file")
        if path.is_file():
            total += info.st_size
            if info.st_nlink != 1 or info.st_size > MAX_MEMBER or total > MAX_TOTAL:
                raise ValueError("Portable byte/link budget exceeded")
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as output:
        for path in files:
            if path.is_file():
                output.write(path, path.relative_to(bundle).as_posix())
    with archive.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def extract_archive(archive: Path, destination: Path) -> None:
    """Validate names/budgets first, then bound streamed bytes and exclusive writes."""
    with zipfile.ZipFile(archive) as package:
        members = package.infolist()
        if not members or len(members) > MAX_MEMBERS:
            raise ValueError("Portable archive member budget exceeded")
        names: set[str] = set()
        total = 0
        for member in members:
            path = PurePosixPath(member.filename)
            if (
                not member.filename
                or member.orig_filename != member.filename
                or "\\" in member.filename
                or ":" in member.filename
                or path.is_absolute()
                or any(part in (".", "..") for part in path.parts)
                or any(
                    part.endswith((" ", ".")) or part.split(".")[0].upper() in RESERVED
                    for part in path.parts
                )
                or str(path).casefold() in names
                or stat.S_IFMT(member.external_attr >> 16) not in (0, stat.S_IFREG, stat.S_IFDIR)
                or not 0 <= member.file_size <= MAX_MEMBER
            ):
                raise ValueError("Unsafe or ambiguous portable archive member")
            names.add(str(path).casefold())
            total += member.file_size
            if total > MAX_TOTAL:
                raise ValueError("Portable archive expanded-byte budget exceeded")
        destination.mkdir()
        actual = 0
        for member in members:
            path = destination.joinpath(*PurePosixPath(member.filename).parts)
            if member.is_dir():
                path.mkdir(parents=True, exist_ok=True)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            count = 0
            with package.open(member) as source, path.open("xb") as output:
                while True:
                    block = source.read(min(BLOCK, MAX_MEMBER - count + 1))
                    if not block:
                        break
                    count += len(block)
                    actual += len(block)
                    if count > member.file_size or count > MAX_MEMBER or actual > MAX_TOTAL:
                        raise ValueError("Portable archive actual bytes exceed their budget")
                    output.write(block)
            if count != member.file_size:
                raise ValueError("Portable archive actual/declaration length mismatch")


def run_application(executable: Path, proof: Path) -> dict:
    """Run the exact extracted product with a new marked profile and system-only executable PATH."""
    prepare_test_root(proof)
    allowed = {"SYSTEMROOT", "WINDIR", "TEMP", "TMP"}
    environment = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    environment["PATH"] = str(Path(os.environ["SYSTEMROOT"]) / "System32")
    phases = []
    for reopen in (False, True):
        arguments = [str(executable), "--native-acceptance-root", str(proof)]
        if reopen:
            arguments.append("--acceptance-reopen")
        # Execute only the fixed just-extracted product, never selected user code.
        result = subprocess.run(arguments, cwd=proof, env=environment, timeout=120, check=False)  # noqa: S603
        phase = "reopen" if reopen else "first"
        receipt = read_small_json(proof / phase / "acceptance.json")
        if result.returncode != 0 or receipt.get("passed") is not True:
            raise ValueError("Actual extracted native workflow failed")
        phases.append(receipt)
    summary = {
        "schema": 1,
        "passed": True,
        "launches": 2,
        "identity": phases[0]["identity"],
        "actualExitCodes": [0, 0],
        "sameRetainedState": phases[0]["retained"] == phases[1]["retained"],
    }
    if not summary["sameRetainedState"]:
        raise ValueError("Native restart changed its retained state")
    (proof / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def prepare_test_root(proof: Path) -> None:
    """Write the exact marker bytes, independent of Windows text newline translation."""
    proof.mkdir()
    (proof / "acceptance.marker").write_bytes(b"ml-observatory-owned-native-acceptance-v1\n")


def read_small_json(path: Path) -> dict:
    """Bound actual opened metadata/receipt bytes, not just caller-supplied size declarations."""
    limit = 8192
    descriptor = os.open(
        path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    )
    with os.fdopen(descriptor, "rb") as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
            raise ValueError("Expected bounded regular package metadata")
        raw = source.read(limit + 1)
    if len(raw) != info.st_size or len(raw) > limit:
        raise ValueError("Package metadata changed or exceeds its limit")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Package metadata must be an object")
    return value


def main(argv: list[str] | None = None) -> int:
    """Relocate/test a fresh candidate while retaining prior outputs and profiles."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("proof", type=Path)
    arguments = parser.parse_args(argv)
    bundle, proof = arguments.bundle.resolve(), arguments.proof.resolve()
    if (
        sys.platform != "win32"
        or not bundle.is_relative_to(ROOT / "release")
        or not proof.is_relative_to(ROOT / "artifacts/native")
        or proof.exists()
    ):
        raise ValueError("Use fresh owned Windows release/proof paths")
    metadata = read_small_json(bundle / "SOURCE.json")
    git = shutil.which("git")
    if git is None:
        raise ValueError("Git must be available to bind the accepted candidate source")
    # The resolved build tool receives only fixed repository metadata arguments.
    source = subprocess.check_output(  # noqa: S603
        [git, "-c", "safe.directory=" + ROOT.as_posix(), "-C", str(ROOT), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    if (
        metadata.get("product") != "ml-model-lifecycle-observatory"
        or metadata.get("version") != "1.1.0"
        or not re.fullmatch("[a-f0-9]{40}", source)
        or metadata.get("source") != source
        or type(metadata.get("sourceDirty")) is not bool
        or (os.environ.get("CI") and metadata["sourceDirty"])
    ):
        raise ValueError("Actual candidate source/version differs from current acceptance source")
    archive = bundle.parent / "MLModelLifecycleObservatory-1.1.0-windows-x64.zip"
    digest = create_archive(bundle, archive)
    sidecar = archive.with_name(archive.name + ".sha256")
    with sidecar.open("x", encoding="ascii") as output:
        output.write(f"{digest}  {archive.name}\n")
    extracted = bundle.parent / "extracted-portable"
    extract_archive(archive, extracted)
    proof.parent.mkdir(parents=True, exist_ok=True)
    summary = run_application(extracted / EXECUTABLE, proof)
    if summary["identity"] != metadata:
        raise ValueError("Extracted executable identity differs from its package record")
    print(json.dumps({"passed": True, "archiveSha256": digest, "launches": 2}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

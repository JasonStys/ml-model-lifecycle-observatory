"""File: scripts/build-native.py
Purpose: Freeze the actual scientific/Tk application into a fresh source-bound Windows directory.
Symbols: main owns public resources; notices reads installed dependency terms.
No installer, normal profile, global change, Docker action or publication occurs.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import secrets
import struct
import subprocess
import sys
import tkinter as tk
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from desktop.workspace import PRODUCT, read_regular  # noqa: E402 - fixed source-root CLI bootstrap
from ml_observatory import VERSION  # noqa: E402 - fixed source-root CLI bootstrap

MIN_NOTICE_BYTES = 100
MAX_NOTICE_BYTES = 65536


def icon(path: Path) -> None:
    """Author a distinct 256-pixel chart glyph directly, without external artwork or tools."""
    size = 256
    bars = ((12, 22, 34, 51), (27, 37, 23, 51), (42, 52, 11, 51))
    pixels = bytearray(size * size * 4)
    for y in range(size):
        for x in range(size):
            u, v = x // 4, y // 4
            bar = any(
                left <= u <= right and top <= v <= bottom for left, right, top, bottom in bars
            )
            color = bytes((155, 224, 110, 255)) if bar else bytes((75, 50, 20, 255))
            offset = ((size - 1 - y) * size + x) * 4
            pixels[offset : offset + 4] = color
    bitmap = struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0, len(pixels), 0, 0, 0, 0)
    image = bitmap + pixels + bytes(size * size // 8)
    directory = struct.pack("<HHHBBBBHHII", 0, 1, 1, 0, 0, 0, 0, 1, 32, len(image), 22)
    with path.open("xb") as output:
        output.write(directory + image)


def command(arguments: list[str], *, timeout: int = 600) -> str:
    """Invoke fixed build tools with vectors, bounded time and no shell expansion."""
    # Only this builder's fixed Git argv is supplied; no application/input content reaches commands.
    return subprocess.check_output(arguments, cwd=ROOT, text=True, timeout=timeout)  # noqa: S603


def notices() -> tuple[bytes, dict[str, str]]:
    """Retain actual Python/Tcl/Tk and scientific-library terms, including DLL zipfs resources."""
    root = tk.Tk()
    root.withdraw()
    versions = {
        "python": platform.python_version(),
        "tcl": str(root.tk.call("info", "patchlevel")),
        "tk": str(root.tk.call("package", "require", "Tk")),
    }
    blocks = [
        ("Authored application - MIT", read_regular(ROOT / "LICENSE")),
        ("Python runtime", read_regular(Path(sys.base_prefix) / "LICENSE.txt")),
    ]
    try:
        for title, directory in [
            ("Tcl", root.tk.call("info", "library")),
            ("Tk", root.tk.eval("set tk_library")),
        ]:
            channel = root.tk.call("open", str(directory) + "/license.terms", "rb")
            try:
                data = root.tk.call("read", channel, 65537)
            finally:
                root.tk.call("close", channel)
            if isinstance(data, str):
                data = data.encode("utf-8")
            if not isinstance(data, bytes) or not MIN_NOTICE_BYTES < len(data) <= MAX_NOTICE_BYTES:
                raise ValueError("Loaded Tcl/Tk notice is missing or exceeds its bound")
            blocks.append((title + " " + versions[title.lower()], data))
    finally:
        root.destroy()
    names = [
        "numpy",
        "scipy",
        "scikit-learn",
        "joblib",
        "threadpoolctl",
        "pydantic",
        "pydantic-core",
        "annotated-types",
        "typing-extensions",
        "typing-inspection",
        "narwhals",
        "pyinstaller",
    ]
    for name in names:
        distribution = importlib.metadata.distribution(name)
        paths = [
            entry
            for entry in distribution.files or []
            if entry.name.upper().startswith(("LICENSE", "COPYING", "NOTICE"))
            and entry.suffix not in (".py", ".pyc")
        ]
        if not paths:
            raise ValueError("Review missing license inventory for " + name)
        blocks.extend(
            (
                name + " " + distribution.version + " / " + entry.name,
                read_regular(Path(distribution.locate_file(entry)), 2 * 1024 * 1024),
            )
            for entry in sorted(paths)
        )
    return b"\n\n".join(title.encode() + b"\n" + data for title, data in blocks), versions


def main(argv: list[str] | None = None) -> int:
    """Require coherent patched build tools and freeze only allowlisted public source/resources."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args(argv)
    if sys.platform != "win32" or sys.version_info[:3] != (3, 14, 10):
        raise ValueError("Native Windows builds require the reviewed CPython3.14.10 SDK")
    if importlib.metadata.version("pyinstaller") != "6.22.3":
        raise ValueError("Reviewed PyInstaller6.22.3 is required")
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    if metadata["name"] != PRODUCT or metadata["version"] != VERSION:
        raise ValueError("Native/core/project product identity differs")
    output = (ROOT / arguments.output).resolve()
    if not output.is_relative_to(ROOT / "release") or output.exists():
        raise ValueError("Choose a new output below release; earlier candidates are preserved")
    git = ["git", "-c", "safe.directory=" + ROOT.as_posix(), "-C", str(ROOT)]
    source = command([*git, "rev-parse", "HEAD"]).strip()
    changed = command([*git, "status", "--porcelain", "--untracked-files=all"]).strip()
    dirty = bool(changed)
    if os.environ.get("CI") and dirty:
        raise ValueError("Hosted native acceptance requires a clean exact checkout")
    if os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("GITHUB_SHA") != source:
        raise ValueError("Hosted native checkout differs from the declared workflow source")
    generated = ROOT / ".runtime" / ("native-metadata-" + secrets.token_hex(8))
    generated.mkdir(parents=True)
    license_bytes, runtime = notices()
    identity = {
        "schema": 1,
        "product": PRODUCT,
        "version": VERSION,
        "source": source,
        "sourceDirty": dirty,
        **runtime,
    }
    (generated / "SOURCE.json").write_text(json.dumps(identity, indent=2) + "\n", encoding="utf-8")
    (generated / "THIRD-PARTY-NOTICES.txt").write_bytes(license_bytes)
    icon(generated / "application.ico")
    # PyInstaller parses this fixed generated version resource; it contains no caller text.
    version_resource = """VSVersionInfo(ffi=FixedFileInfo(filevers=(1,1,0,0),prodvers=(1,1,0,0),
    mask=0x3f,flags=0,OS=0x40004,fileType=1,subtype=0,date=(0,0)),kids=[StringFileInfo([
    StringTable('040904B0',[StringStruct('CompanyName','Jason Stys'),
    StringStruct('FileDescription','ML Model Lifecycle Observatory'),
    StringStruct('FileVersion','1.1.0'),StringStruct('ProductVersion','1.1.0'),
    StringStruct('ProductName','ML Model Lifecycle Observatory')])]),
    VarFileInfo([VarStruct('Translation',[1033,1200])])])"""
    (generated / "version.txt").write_text(version_resource, encoding="utf-8")
    args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onedir",
        "--name",
        "MLModelLifecycleObservatory",
        "--paths",
        str(ROOT),
        "--distpath",
        str(output),
        "--workpath",
        str(generated / "build"),
        "--specpath",
        str(generated),
        "--version-file",
        str(generated / "version.txt"),
        "--icon",
        str(generated / "application.ico"),
        "--add-data",
        str(generated / "application.ico") + ":.",
        "--add-data",
        str(ROOT / "sql") + ":ml_observatory/sql",
        "--add-data",
        str(generated / "SOURCE.json") + ":.",
        "--copy-metadata",
        "scikit-learn",
        "--copy-metadata",
        "numpy",
        str(ROOT / "desktop/launcher.py"),
    ]
    environment = {**os.environ, "PYINSTALLER_CONFIG_DIR": str(generated / "cache")}
    # Fixed reviewed PyInstaller argv; user datasets and model files are never executed.
    subprocess.run(args, cwd=ROOT, check=True, timeout=600, env=environment)  # noqa: S603
    if (
        command([*git, "rev-parse", "HEAD"]).strip() != source
        or command([*git, "status", "--porcelain", "--untracked-files=all"]).strip() != changed
    ):
        raise ValueError("Source identity changed during native build")
    bundle = output / "MLModelLifecycleObservatory"
    for original, name in [
        (ROOT / "LICENSE", "LICENSE.txt"),
        (generated / "SOURCE.json", "SOURCE.json"),
        (generated / "THIRD-PARTY-NOTICES.txt", "THIRD-PARTY-NOTICES.txt"),
    ]:
        (bundle / name).write_bytes(read_regular(original))
    executable = bundle / "MLModelLifecycleObservatory.exe"
    with executable.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    print(json.dumps({"built": True, "identity": identity, "executableSha256": digest}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

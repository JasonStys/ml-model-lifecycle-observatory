"""File: desktop/launcher.py
Purpose: Open the genuine native model workbench with an identified durable profile.
Symbols: main owns the window/profile lifecycle; optional profile is an explicit user-selected path.
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import sqlite3
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from desktop.acceptance import exercise
from desktop.application import Application
from desktop.workspace import PRODUCT, Workspace, default_profile, read_regular, strict_json
from ml_observatory import VERSION


def package_identity() -> dict:
    """Require coherent product/source/runtime metadata in a frozen application."""
    if not getattr(sys, "frozen", False):
        return {"product": PRODUCT, "version": VERSION, "mode": "development"}
    root = Path(sys._MEIPASS)
    value = strict_json(read_regular(root / "SOURCE.json", 8192).decode("utf-8"))
    if (
        not isinstance(value, dict)
        or set(value)
        != {"schema", "product", "version", "source", "sourceDirty", "python", "tcl", "tk"}
        or type(value["schema"]) is not int
        or value["schema"] != 1
        or value.get("product") != PRODUCT
        or value.get("version") != VERSION
        or value.get("python") != platform.python_version()
        or type(value.get("sourceDirty")) is not bool
        or not isinstance(value.get("source"), str)
        or not re.fullmatch(r"[a-f0-9]{40}", value["source"])
        or not isinstance(value["tcl"], str)
        or not isinstance(value["tk"], str)
    ):
        raise ValueError("Frozen application identity does not match the loaded runtime")
    return value


def parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    """Validate explicit profiles and test markers before constructing a window or store."""
    parser = argparse.ArgumentParser(description="ML Model Lifecycle Observatory by Jason Stys")
    parser.add_argument(
        "--profile", type=Path, help="Explicit empty or identified OS-local profile"
    )
    parser.add_argument(
        "--runtime-info", action="store_true", help="Read package/runtime only; no profile"
    )
    parser.add_argument(
        "--runtime-info-output", type=Path, help="Write runtime-only identity to a NEW local file"
    )
    parser.add_argument(
        "--native-acceptance-root",
        type=Path,
        help="Explicit marked synthetic acceptance directory; no normal profile",
    )
    parser.add_argument("--acceptance-reopen", action="store_true")
    arguments = parser.parse_args(argv)
    if arguments.runtime_info_output and not arguments.runtime_info:
        parser.error("--runtime-info-output requires --runtime-info")
    if arguments.acceptance_reopen and not arguments.native_acceptance_root:
        parser.error("--acceptance-reopen requires its marked acceptance root")
    if arguments.native_acceptance_root:
        if arguments.profile or arguments.runtime_info:
            parser.error("Acceptance cannot select another profile or runtime-only mode")
        marker = arguments.native_acceptance_root / "acceptance.marker"
        if read_regular(marker, 128) != b"ml-observatory-owned-native-acceptance-v1\n":
            raise ValueError("Synthetic acceptance marker does not match")
        if (arguments.native_acceptance_root / "profile").exists() != arguments.acceptance_reopen:
            raise ValueError("Use a fresh marked directory or explicitly reopen its test profile")
    return arguments


def emit_runtime_info(arguments: argparse.Namespace, identity: dict, runtime: dict) -> None:
    """Report actual package/runtime identity without opening a normal or test profile."""
    rendered = json.dumps({"package": identity, "runtime": runtime}) + "\n"
    if arguments.runtime_info_output:
        with arguments.runtime_info_output.open("x", encoding="utf-8") as output:
            output.write(rendered)
    elif sys.stdout is not None:
        print(rendered, end="", flush=True)
    else:
        raise ValueError("Windowed runtime inspection requires a new output file")


def main(argv: list[str] | None = None) -> int:
    """Start normal native controls; retain real work before releasing profile ownership."""
    arguments = parse_arguments(argv)
    root = tk.Tk()
    root.withdraw()
    workspace = None
    application = None
    try:
        identity = package_identity()
        if getattr(sys, "frozen", False):
            icon = Path(sys._MEIPASS) / "application.ico"
            read_regular(icon, 512 * 1024)
            root.iconbitmap(str(icon))
        runtime = {
            "python": platform.python_version(),
            "tcl": str(root.tk.call("info", "patchlevel")),
            "tk": str(root.tk.call("package", "require", "Tk")),
        }
        if getattr(sys, "frozen", False) and any(identity[key] != runtime[key] for key in runtime):
            raise ValueError("Actual loaded native runtime does not match the package record")
        if arguments.runtime_info:
            emit_runtime_info(arguments, identity, runtime)
            root.destroy()
            return 0
        profile = (
            arguments.native_acceptance_root / "profile"
            if arguments.native_acceptance_root
            else arguments.profile or default_profile()
        )
        workspace = Workspace(profile)
        application = Application(root, workspace)
        root.deiconify()
        if arguments.native_acceptance_root:
            exercise(
                application,
                arguments.native_acceptance_root
                / ("reopen" if arguments.acceptance_reopen else "first"),
                identity,
                reopen=arguments.acceptance_reopen,
            )
        while not application.closed:
            try:
                root.mainloop()
            except KeyboardInterrupt:
                application.close()
        return 0 if not arguments.native_acceptance_root or application.acceptance_passed else 2
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as error:
        if arguments.native_acceptance_root:
            failure = arguments.native_acceptance_root / "startup-failure.json"
            with failure.open("x", encoding="utf-8") as output:
                json.dump({"passed": False, "errorType": type(error).__name__}, output)
        else:
            messagebox.showerror("Model workbench could not open", str(error), parent=root)
        root.destroy()
        return 2
    finally:
        if application is not None and application.worker is not None:
            application.worker.join()
        if workspace is not None:
            workspace.close()


if __name__ == "__main__":
    raise SystemExit(main())

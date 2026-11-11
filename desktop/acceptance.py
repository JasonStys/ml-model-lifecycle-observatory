"""File: desktop/acceptance.py
Purpose: Drive the actual packaged native widgets/core only inside a marked synthetic profile.
Symbols: capture owns this window; exercise advances on actual task completion.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import struct
import sys
import time
import zlib
from ctypes import wintypes
from pathlib import Path

from desktop import application
from desktop.application import Application
from desktop.workspace import read_regular
from ml_observatory import VERSION

MAX_DIMENSION = 4096
PREPARED_ROWS = 1200
EXPECTED_MODELS = 2
EXPECTED_FEATURES = 8


def require(condition: bool, message: str) -> None:
    """Keep every native acceptance oracle active under optimized Python as well."""
    if not condition:
        raise ValueError(message)


def capture(window: Application, target: Path) -> None:
    """Capture this owned Tk window via PrintWindow; never capture the whole desktop."""
    if sys.platform != "win32":
        raise OSError("native screenshot acceptance targets Windows")
    load = ctypes.WinDLL
    user, gdi = load("user32", use_last_error=True), load("gdi32", use_last_error=True)
    pointer = ctypes.c_void_p
    for library, name, arguments, result in [
        (user, "GetAncestor", [pointer, ctypes.c_uint], pointer),
        (user, "GetWindowDC", [pointer], pointer),
        (gdi, "CreateCompatibleDC", [pointer], pointer),
        (gdi, "CreateCompatibleBitmap", [pointer, ctypes.c_int, ctypes.c_int], pointer),
        (gdi, "SelectObject", [pointer, pointer], pointer),
        (gdi, "DeleteObject", [pointer], ctypes.c_int),
        (gdi, "DeleteDC", [pointer], ctypes.c_int),
        (user, "ReleaseDC", [pointer, pointer], ctypes.c_int),
        (user, "PrintWindow", [pointer, pointer, ctypes.c_uint], ctypes.c_int),
        (user, "GetWindowRect", [pointer, ctypes.POINTER(wintypes.RECT)], ctypes.c_int),
        (
            gdi,
            "GetDIBits",
            [pointer, pointer, ctypes.c_uint, ctypes.c_uint, pointer, pointer, ctypes.c_uint],
            ctypes.c_int,
        ),
    ]:
        function = getattr(library, name)
        function.argtypes, function.restype = arguments, result
    window.root.update_idletasks()
    handle = user.GetAncestor(window.root.winfo_id(), 2)
    rectangle = wintypes.RECT()
    if not user.GetWindowRect(handle, ctypes.byref(rectangle)):
        raise OSError("owned window bounds unavailable")
    width, height = rectangle.right - rectangle.left, rectangle.bottom - rectangle.top
    if not 1 <= width <= MAX_DIMENSION or not 1 <= height <= MAX_DIMENSION:
        raise OSError("owned screenshot outside bounded dimensions")
    source = user.GetWindowDC(handle)
    destination = gdi.CreateCompatibleDC(source)
    bitmap = gdi.CreateCompatibleBitmap(source, width, height)
    previous = gdi.SelectObject(destination, bitmap)
    try:
        if not user.PrintWindow(handle, destination, 2):
            raise OSError("owned window rendering unavailable")
        gdi.SelectObject(destination, previous)
        pixels = ctypes.create_string_buffer(width * height * 4)
        header = ctypes.create_string_buffer(
            struct.pack(
                "<IiiHHIIiiII", 40, width, -height, 1, 32, 0, width * height * 4, 0, 0, 0, 0
            )
        )
        if gdi.GetDIBits(source, bitmap, 0, height, pixels, header, 0) != height:
            raise OSError("owned screenshot pixels incomplete")
        raw = pixels.raw
        scanlines = bytearray()
        for row in range(height):
            scanlines.append(0)
            for column in range(width):
                offset = (row * width + column) * 4
                scanlines.extend((raw[offset + 2], raw[offset + 1], raw[offset]))

        def chunk(name: bytes, data: bytes) -> bytes:
            """Encode a bounded standard PNG chunk with its actual CRC."""
            return (
                struct.pack(">I", len(data))
                + name
                + data
                + struct.pack(">I", zlib.crc32(name + data))
            )

        target.write_bytes(
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(scanlines)))
            + chunk(b"IEND", b"")
        )
    finally:
        gdi.SelectObject(destination, previous)
        gdi.DeleteObject(bitmap)
        gdi.DeleteDC(destination)
        user.ReleaseDC(handle, source)


def exercise(window: Application, output: Path, identity: dict, *, reopen: bool) -> None:  # noqa: PLR0915 - ordered native acceptance phases share only their synthetic context
    """Advance real native controls on completion and record independent domain oracles."""
    output.mkdir(mode=0o700)
    deadline = time.monotonic() + 90
    receipt = {
        "schema": 1,
        "version": VERSION,
        "identity": identity,
        "pid": os.getpid(),
        "reopen": reopen,
        "passed": False,
        "steps": [],
        "scope": "Actual packaged Tk/core; marked synthetic profile only",
    }
    answer = True
    application.messagebox.askyesno = lambda *_args, **_kwargs: answer
    original_export = application.filedialog.asksaveasfilename
    chosen_export = output / "model-evidence.json"
    application.filedialog.asksaveasfilename = lambda **_kwargs: str(chosen_export)
    window.acceptance_passed = False

    def step(name: str) -> None:
        """Retain public boolean/count evidence without private paths or raw data."""
        receipt["steps"].append(name)

    def first_journey():  # noqa: PLR0915 - preserve explicit sequential independent UI oracles
        """Train/register/edit/review/predict/drift/export through real widget bindings."""
        nonlocal answer
        window.prepare_button.invoke()
        text = window.dataset.get("1.0", "end-1c")
        require(len(text.splitlines()) == PREPARED_ROWS, "Prepared dataset row count differs")
        window.validate_button.invoke()
        require("Validated 1200" in window.status.get(), "Actual dataset validation missing")
        require(not window.workspace.dataset.exists(), "Preparation unexpectedly saved data")
        window.train_button.invoke()
        require(window.busy, "Training did not start")
        yield
        models = window.workspace.models()
        require(len(models) == EXPECTED_MODELS, "Original two algorithms were not registered")
        require({row["status"] for row in models} == {"candidate"}, "Training auto-promoted")
        require(len(window.tree.get_children()) == EXPECTED_MODELS, "Registry UI differs from data")
        step("editable data and real two-candidate training; no automatic promotion")
        selected = next(
            row["model_id"]
            for row in models
            if window.workspace.review(row["model_id"])["eligible_on_recorded_quality"]
        )
        window.tree.selection_set(selected)
        window.review_button.invoke()
        yield
        dossier = window.last_evidence
        require(
            dossier["model_id"] == selected and dossier["provenance_verified"],
            "Dossier identity differs",
        )
        require(not dossier["dataset_bytes_verified"], "Dossier overstated its verification scope")
        window.tabs.select(window.models_tab)
        capture(window, output / "native-registry.png")
        answer = False
        window.promote_button.invoke()
        require(
            {row["status"] for row in window.workspace.models()} == {"candidate"},
            "Cancelled promotion changed state",
        )
        answer = True
        window.promote_button.invoke()
        yield
        require(
            window.workspace.review(selected)["status"] == "champion", "Explicit promotion failed"
        )
        other = next(row["model_id"] for row in models if row["model_id"] != selected)
        window.tree.selection_set(other)
        window.traffic.set("0")
        next(button for button in window.controls if button["text"] == "Assign challenger").invoke()
        yield
        require(window.last_evidence["model_id"] == other, "Shadow assignment did not finish")
        window.sample()
        window.predict_button.invoke()
        yield
        prediction = window.last_evidence
        require(prediction["model_id"] == selected, "Shadow-only routing changed served model")
        require(prediction["challenger_model_id"] == other, "Actual challenger observation missing")
        require(0 <= prediction["failure_probability"] <= 1, "Probability outside valid domain")
        step("verified dossier, cancelled/accepted promotion and actual shadow prediction")
        window.tree.selection_set(selected)
        next(
            button
            for button in window.controls
            if button["text"] == "Compute selected model PSI from dataset"
        ).invoke()
        yield
        require(
            window.last_evidence["sample_count"] == PREPARED_ROWS, "PSI did not use actual data"
        )
        require(
            len(window.last_evidence["features"]) == EXPECTED_FEATURES,
            "Feature evidence incomplete",
        )
        window.review_button.invoke()
        yield
        capture(window, output / "native-dossier.png")
        next(
            button
            for button in window.controls
            if button["text"] == "Export evidence to NEW JSON file"
        ).invoke()
        # JSON arrays are lists after decoding; the verified Python dossier contains tuples.
        expected_json = json.loads(json.dumps(window.last_evidence, allow_nan=False))
        require(json.loads(read_regular(chosen_export)) == expected_json, "Actual export differs")
        preserved = read_regular(chosen_export)
        next(
            button
            for button in window.controls
            if button["text"] == "Export evidence to NEW JSON file"
        ).invoke()
        require(read_regular(chosen_export) == preserved, "Export overwrote earlier evidence")
        saved_data = read_regular(window.workspace.dataset)
        window._replace(window.dataset, "malformed JSON")
        window.train_button.invoke()
        yield
        require("Operation failed" in window.status.get(), "Invalid dataset was accepted")
        require(
            read_regular(window.workspace.dataset) == saved_data,
            "Invalid edit replaced stored data",
        )
        window._replace(window.dataset, text)
        step("actual PSI/export, existing-file refusal and invalid dataset preservation")
        receipt["retained"] = {
            "models": sorted(row["model_id"] for row in window.workspace.models()),
            "champion": selected,
            "datasetSha256": hashlib.sha256(saved_data).hexdigest(),
        }

    def reopen_journey():
        """Reopen actual registry and data without retraining or inventing history."""
        prior = json.loads(read_regular(output.parent / "first" / "acceptance.json"))
        retained = prior["retained"]
        models = window.workspace.models()
        require(
            sorted(row["model_id"] for row in models) == retained["models"],
            "Reopen lost model identities",
        )
        require(
            hashlib.sha256(read_regular(window.workspace.dataset)).hexdigest()
            == retained["datasetSha256"],
            "Reopen changed dataset bytes",
        )
        selected = retained["champion"]
        require(window.workspace.review(selected)["status"] == "champion", "Reopen lost champion")
        window.tree.selection_set(selected)
        window.review_button.invoke()
        yield
        require(
            window.last_evidence["provenance_verified"], "Reopened artifact failed verification"
        )
        window.sample()
        window.predict_button.invoke()
        yield
        require(window.last_evidence["model_id"] == selected, "Reopened prediction routing changed")
        receipt["retained"] = retained
        step("same actual models/champion/dataset and inference survive native restart")

    journey = reopen_journey() if reopen else first_journey()

    def complete(error: Exception | None = None) -> None:
        """Preserve the actual result and request ordinary completion-aware native shutdown."""
        nonlocal answer
        answer = True
        application.filedialog.asksaveasfilename = original_export
        receipt["passed"] = error is None
        if error is not None:
            receipt["error"] = f"{type(error).__name__}: {error}"[:500]
        (output / "acceptance.json").write_text(
            json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
        )
        window.acceptance_passed = error is None
        window.close()

    def advance() -> None:
        """Poll only actual retained task completion under a fixed whole-journey deadline."""
        try:
            require(time.monotonic() < deadline, "Native workflow acceptance deadline exceeded")
            if window.busy:
                window.root.after(30, advance)
                return
            next(journey)
        except StopIteration:
            complete()
            return
        except Exception as error:
            complete(error)
            return
        window.root.after(0, advance)

    window.root.after_idle(advance)

"""File: native_tests/test_widgets.py
Purpose: Exercise real Tk authoring/review controls against actual synthetic model operations.
Symbols: finish waits on real UI completion; profiles are fresh and never the default user store.
"""

import json
import threading
import time
import tkinter as tk
from pathlib import Path

import pytest

from desktop import application
from desktop.workspace import Workspace


def finish(root: tk.Tk, view: application.Application) -> None:
    """Drive the real GUI until retained work completes or a fixed deadline fails."""
    deadline = time.monotonic() + 30
    done = tk.BooleanVar(root, value=False)

    def inspect() -> None:
        if not view.busy or time.monotonic() >= deadline:
            done.set(True)
        else:
            root.after(20, inspect)

    root.after(0, inspect)
    root.wait_variable(done)
    assert not view.busy, "Actual model operation did not finish within the GUI test budget"


@pytest.fixture
def native(tmp_path: Path):
    """Create the real native widget tree over one empty fictional local profile."""
    workspace = Workspace(tmp_path / "profile")
    root = tk.Tk()
    view = application.Application(root, workspace)
    root.update()
    yield root, view, workspace
    if view.worker is not None:
        view.worker.join(timeout=30)
        assert not view.worker.is_alive()
    workspace.close()
    if not view.closed:
        root.destroy()


def test_real_editor_training_dossier_promotion_prediction_and_invalid_input(native, monkeypatch):
    """Exercise real button handlers, trained artifacts and native widgets."""
    root, view, workspace = native
    view.prepare_button.invoke()
    assert len(view.dataset.get("1.0", "end-1c").splitlines()) == 1200
    view.validate_button.invoke()
    assert "Validated 1200" in view.status.get()
    view.train_button.invoke()
    assert view.busy and str(view.train_button["state"]) == "disabled"
    finish(root, view)
    assert len(view.tree.get_children()) == 2
    assert {row["status"] for row in workspace.models()} == {"candidate"}
    selected = next(
        row["model_id"]
        for row in workspace.models()
        if workspace.review(row["model_id"])["eligible_on_recorded_quality"]
    )
    view.tree.selection_set(selected)
    view.review_button.invoke()
    finish(root, view)
    assert json.loads(view.evidence.get("1.0", "end-1c"))["model_id"] == selected
    assert view.tree.selection() == (selected,)
    monkeypatch.setattr(application.messagebox, "askyesno", lambda *_args, **_kwargs: False)
    view.promote_button.invoke()
    assert {row["status"] for row in workspace.models()} == {"candidate"}
    monkeypatch.setattr(application.messagebox, "askyesno", lambda *_args, **_kwargs: True)
    view.promote_button.invoke()
    finish(root, view)
    assert workspace.review(selected)["status"] == "champion"
    view.sample()
    view.predict_button.invoke()
    finish(root, view)
    assert view.last_evidence["model_id"] == selected
    assert 0 <= view.last_evidence["failure_probability"] <= 1
    retained = workspace.dataset.read_bytes()
    view._replace(view.dataset, "malformed JSON")
    view.train_button.invoke()
    finish(root, view)
    assert "Operation failed" in view.status.get()
    assert workspace.dataset.read_bytes() == retained
    assert workspace.review(selected)["status"] == "champion"


def test_busy_close_retains_ownership_until_actual_work_completion(native, monkeypatch):
    """Confirmed Quit retains profile ownership until the real background operation finishes."""
    root, view, workspace = native
    started, release = threading.Event(), threading.Event()

    def retained_work():
        started.set()
        if not release.wait(5):
            raise RuntimeError("Test did not release its owned worker")
        return {"completed": True}

    view.run(retained_work)
    assert started.wait(2)
    monkeypatch.setattr(application.messagebox, "askyesno", lambda *_args, **_kwargs: False)
    view.close()
    assert not view.closing and not view.closed
    monkeypatch.setattr(application.messagebox, "askyesno", lambda *_args, **_kwargs: True)
    view.close()
    assert view.closing and not view.closed and workspace.descriptor >= 0
    with pytest.raises((OSError, ValueError)):
        Workspace(workspace.directory)
    release.set()
    root.mainloop()
    assert view.closed and workspace.descriptor == -1
    reopened = Workspace(workspace.directory)
    reopened.close()


def test_actual_window_minimum_keeps_exit_and_help_available(native):
    """Visible lifecycle controls remain on screen at the application's declared minimum size."""
    root, view, _ = native
    root.geometry("980x700")
    root.update()
    button = view.quit_button
    assert button.winfo_viewable()
    assert button.winfo_rooty() + button.winfo_height() <= root.winfo_rooty() + root.winfo_height()
    view.tabs.select(view.help_tab)
    root.update()
    assert view.tabs.select() == str(view.help_tab)

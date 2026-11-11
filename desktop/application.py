"""File: desktop/application.py
Purpose: Provide genuine native authoring, training, review and explicit model-operations
controls.
Symbols and variables: see docs/code-index.md; Application retains one Workspace and
background task.
Prepared observations are editable data in this application, never a separate demonstration
program.
"""

from __future__ import annotations

import json
import queue
import threading
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any

from desktop.workspace import Workspace, export_new, parse_dataset, read_regular
from ml_observatory import VERSION


class Application:
    """A single-owner offline workbench over the existing verified model/registry contracts."""

    def __init__(self, root: tk.Tk, workspace: Workspace):
        """Build normal controls; retain pending native work and show explicit errors/results."""
        self.root, self.workspace = root, workspace
        self.busy = False
        self.closing = False
        self.closed = False
        self.results: queue.Queue[tuple[bool, Any]] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.on_result: Callable[[Any], None] | None = None
        self.last_evidence: Any = None
        self.controls: list[ttk.Button] = []
        self.status = tk.StringVar(
            value="Local workspace ready. Prepare/import data, then train candidates."
        )
        self.count = tk.StringVar(value="1200")
        self.seed = tk.StringVar(value="20260917")
        self.reason = tk.StringVar(value="Reviewed recorded quality and provenance")
        self.traffic = tk.StringVar(value="0")
        root.title(f"ML Model Lifecycle Observatory {VERSION} — Jason Stys")
        root.geometry("1260x860")
        root.minsize(980, 700)
        root.protocol("WM_DELETE_WINDOW", self.close)
        shell = ttk.Frame(root, padding=18)
        shell.pack(fill="both", expand=True)
        ttk.Label(
            shell, text="ML Model Lifecycle Observatory", font=("TkDefaultFont", 21, "bold")
        ).pack(anchor="w")
        ttk.Label(
            shell, text=f"Jason Stys · v{VERSION} · offline, trusted OS-owner workspace"
        ).pack(anchor="w", pady=5)
        ttk.Label(
            shell,
            text=(
                "Synthetic service-health models only. Review evidence before deployment; "
                "no automatic promotion, external telemetry or network service."
            ),
            wraplength=1120,
        ).pack(anchor="w", pady=(0, 12))
        footer = ttk.Frame(shell)
        footer.pack(side="bottom", fill="x", pady=(12, 0))
        ttk.Label(footer, textvariable=self.status, wraplength=970).pack(
            side="left", fill="x", expand=True
        )
        self.quit_button = ttk.Button(footer, text="Quit application", command=self.close)
        self.quit_button.pack(side="right")
        self.tabs = ttk.Notebook(shell)
        self.tabs.pack(fill="both", expand=True)
        self.data_tab = self._tab("1 · Dataset")
        self.models_tab = self._tab("2 · Registry & deployment")
        self.predict_tab = self._tab("3 · Predict & drift")
        self.evidence_tab = self._tab("4 · Evidence")
        self.help_tab = self._tab("Help & privacy")
        self._data_controls()
        self._model_controls()
        self._prediction_controls()
        self.evidence = ScrolledText(self.evidence_tab, wrap="word", font=("Consolas", 10))
        self.evidence.pack(fill="both", expand=True)
        self._button(self.evidence_tab, "Export evidence to NEW JSON file", self.export).pack(
            anchor="e", pady=10
        )
        help_text = ScrolledText(self.help_tab, wrap="word", font=("TkDefaultFont", 11))
        help_text.pack(fill="both", expand=True)
        help_text.insert(
            "1.0",
            """HOW TO USE THIS APPLICATION
1. Prepare 400-4000 fictional JSON Lines rows, or import your authorized local data.
Edit/validate before training. Training saves the current dataset and trains both original
logistic and compact MLP candidates with disjoint train/calibration/test partitions.
2. Select a registry row and Verify dossier. Inspect artifact/dataset identities, split
counts, recorded metrics, gates and deployment history. The dossier verifies bundle bytes
and registered metadata, not fresh metric evaluation or raw training data.
3. Promote only after review and confirmation, with a useful reason. It never happens
automatically. Configure a different challenger at 0% for shadow or 1-50% for deterministic
canary routing. Rollback uses the original audited history and can legitimately be
unavailable.
4. Edit one schema-valid observation and Predict through the actual champion/challenger
service. PSI uses the current validated dataset; it is context, not confidence, fresh
quality proof or an instruction to promote. Select Evidence and export a NEW file; existing
files are never overwritten.

DATA AND PRIVACY
Your identified SQLite registry, JSON datasets and content-addressed JSON model artifacts
persist outside the program folder. They are local plaintext readable by this OS owner. No
sign-in, cloud sync, public API, arbitrary executable model import, network fetching or
telemetry is added. Use fictional or appropriately authorized/deidentified data. The native
ownership lock prevents accidental concurrent app instances; it is not protection against a
malicious OS owner or another trusted CLI changing files.

EXIT AND RECOVERY
Close asks for confirmation. If training is active, the window retains ownership until its
real work completes; no thread is killed or database swapped. Do not move individual program
files; keep the full extracted portable folder. An unknown/nonempty profile is refused, not
reset. Preserve the complete profile before recovery.

LIMITS
This is a bounded educational service-health lifecycle, not a universal model trainer or a
safety-critical production controller. Original raw-data verification and 100-entry history
bounds remain. Desktop composition/GUI acceptance is separate from the core package coverage
denominator. Windows portable build is unsigned.

AUTHOR / SOURCE / CONTACT
Jason Stys · https://github.com/JasonStys/ml-model-lifecycle-observatory
""",
        )
        help_text.configure(state="disabled")
        self.refresh_models()
        if workspace.dataset.exists():
            self._replace(self.dataset, read_regular(workspace.dataset).decode("utf-8"))
        root.after(40, self._poll)

    def _tab(self, caption: str) -> ttk.Frame:
        """Create one named normal navigation panel within this real application."""
        frame = ttk.Frame(self.tabs, padding=14)
        self.tabs.add(frame, text=caption)
        return frame

    def _button(self, parent: ttk.Frame, caption: str, action: Callable[[], None]) -> ttk.Button:
        """Retain operation buttons so one active task can disable overlapping mutations."""
        button = ttk.Button(parent, text=caption, command=action)
        self.controls.append(button)
        return button

    def _data_controls(self) -> None:
        """Expose bounded data preparation, import, validation and real candidate training."""
        row = ttk.Frame(self.data_tab)
        row.pack(fill="x", pady=(0, 10))
        for label, variable, width in [("Prepared rows", self.count, 8), ("Seed", self.seed, 14)]:
            ttk.Label(row, text=label).pack(side="left", padx=(0, 5))
            ttk.Entry(row, textvariable=variable, width=width).pack(side="left", padx=(0, 16))
        self.prepare_button = self._button(row, "Prepare editable data", self.prepare)
        self.prepare_button.pack(side="left", padx=4)
        self._button(row, "Import JSON Lines", self.import_dataset).pack(side="left", padx=4)
        self.validate_button = self._button(row, "Validate dataset", self.validate)
        self.validate_button.pack(side="left", padx=4)
        self.train_button = self._button(row, "Save dataset & train candidates", self.train)
        self.train_button.pack(side="left", padx=4)
        ttk.Label(
            self.data_tab,
            text=(
                "Editable labeled observations · 5 MiB / 400-4000 rows · "
                "training never promotes a model"
            ),
        ).pack(anchor="w", pady=(0, 8))
        self.dataset = ScrolledText(self.data_tab, wrap="none", font=("Consolas", 9), undo=True)
        self.dataset.pack(fill="both", expand=True)

    def _model_controls(self) -> None:
        """Present actual registry rows alongside explicit audited deployment controls."""
        self.tree = ttk.Treeview(
            self.models_tab,
            columns=("algorithm", "status", "auc", "brier"),
            show="tree headings",
            height=10,
            selectmode="browse",
        )
        for field, caption, width in [
            ("#0", "Content-addressed model ID", 360),
            ("algorithm", "Algorithm", 150),
            ("status", "Registry status", 130),
            ("auc", "Recorded ROC AUC", 140),
            ("brier", "Recorded Brier", 140),
        ]:
            self.tree.heading(field, text=caption)
            self.tree.column(field, width=width, stretch=field == "#0")
        self.tree.pack(fill="both", expand=True)
        row = ttk.Frame(self.models_tab)
        row.pack(fill="x", pady=12)
        self.review_button = self._button(row, "Verify selected dossier", self.review)
        self.review_button.pack(side="left", padx=4)
        self._button(row, "Refresh registry", self.refresh_models).pack(side="left", padx=4)
        ttk.Label(row, text="Challenger traffic (0-50%)").pack(side="left", padx=(14, 5))
        ttk.Entry(row, textvariable=self.traffic, width=5).pack(side="left")
        self._button(row, "Assign challenger", self.challenger).pack(side="left", padx=8)
        ttk.Label(self.models_tab, text="Independent review reason (10-300 characters)").pack(
            anchor="w"
        )
        ttk.Entry(self.models_tab, textvariable=self.reason).pack(fill="x", pady=5)
        row = ttk.Frame(self.models_tab)
        row.pack(fill="x", pady=8)
        self.promote_button = self._button(row, "Review & promote selected", self.promote)
        self.promote_button.pack(side="left", padx=4)
        self._button(row, "Rollback prior champion", self.rollback).pack(side="left", padx=4)
        ttk.Label(
            self.models_tab,
            text=(
                "These actions change this local registry only. Existing "
                "service/API deployments are not connected."
            ),
            wraplength=1000,
        ).pack(anchor="w")

    def _prediction_controls(self) -> None:
        """Let users edit schema-complete observation JSON and request real inference/PSI."""
        row = ttk.Frame(self.predict_tab)
        row.pack(fill="x", pady=8)
        self._button(row, "Use first dataset observation", self.sample).pack(side="left", padx=4)
        self.predict_button = self._button(row, "Predict via active registry", self.predict)
        self.predict_button.pack(side="left", padx=4)
        self._button(row, "Compute selected model PSI from dataset", self.drift).pack(
            side="left", padx=4
        )
        self.observation = ScrolledText(self.predict_tab, wrap="none", font=("Consolas", 11))
        self.observation.pack(fill="both", expand=True)

    @staticmethod
    def _replace(widget: ScrolledText, text: str) -> None:
        """Replace a UI-owned editor from a validated operation on the main Tk thread."""
        widget.delete("1.0", "end")
        widget.insert("1.0", text)

    def _selected(self) -> str:
        """Require a concrete selected model identity before a registry action."""
        selection = self.tree.selection()
        if not selection:
            raise ValueError("Select a registered model first")
        return selection[0]

    def _text(self) -> str:
        """Read the current editable dataset with an early character budget."""
        text = self.dataset.get("1.0", "end-1c")
        if len(text) > 5 * 1024 * 1024:
            raise ValueError("Dataset exceeds the input budget")
        return text

    def run(
        self, operation: Callable[[], Any], callback: Callable[[Any], None] | None = None
    ) -> None:
        """Run one retained operation; no Tk widget is read/written by the worker thread."""
        if self.busy or self.closing:
            return
        self.busy = True
        self.on_result = callback or self.show_evidence
        self.status.set("Working locally; keep this window open. No automatic deployment.")
        for control in self.controls:
            control.configure(state="disabled")
        self.dataset.configure(state="disabled")
        self.observation.configure(state="disabled")

        def work() -> None:
            try:
                self.results.put((True, operation()))
            except Exception as error:
                self.results.put((False, f"{type(error).__name__}: {error}"[:600]))

        self.worker = threading.Thread(target=work, name="owned-model-operation")
        self.worker.start()

    def _poll(self) -> None:
        """Consume a real completion on the UI thread; keep profile ownership until the worker has
        joined."""
        try:
            success, value = self.results.get_nowait()
        except queue.Empty:
            self.root.after(40, self._poll)
            return
        assert self.worker is not None
        self.worker.join()
        self.busy = False
        for control in self.controls:
            control.configure(state="normal")
        self.dataset.configure(state="normal")
        self.observation.configure(state="normal")
        if success:
            if self.on_result:
                self.on_result(value)
            self.status.set("Completed. Review actual evidence and limits; nothing was published.")
            self.refresh_models()
        else:
            self.status.set("Operation failed; inspect input/state and retry explicitly. " + value)
        if self.closing:
            self._finish_close()
        else:
            self.root.after(40, self._poll)

    def guarded(self, operation: Callable[[], None]) -> None:
        """Surface invalid input from immediate widget handlers without changing stored state."""
        try:
            operation()
        except (ValueError, OSError, KeyError, RuntimeError) as error:
            self.status.set(f"Cannot perform action: {error}"[:600])

    def prepare(self) -> None:
        """Replace only the unsaved editor with explicitly requested synthetic observations."""
        self.guarded(
            lambda: self._replace(
                self.dataset, self.workspace.prepare(int(self.count.get()), int(self.seed.get()))
            )
        )

    def import_dataset(self) -> None:
        """Validate user-selected local bytes before replacing their current editable draft."""

        def action() -> None:
            path = filedialog.askopenfilename(
                parent=self.root,
                title="Open authorized JSON Lines dataset",
                filetypes=[("JSON Lines", "*.jsonl"), ("Text", "*.txt")],
            )
            if path:
                text = read_regular(Path(path)).decode("utf-8")
                parse_dataset(text)
                self._replace(self.dataset, text)
                self.status.set(
                    "Validated data imported into editor only; review before training/saving."
                )

        self.guarded(action)

    def validate(self) -> None:
        """Report actual row validation without saving or training anything."""

        def action() -> None:
            records = parse_dataset(self._text())
            self.status.set(f"Validated {len(records)} labeled rows; no registry mutation.")

        self.guarded(action)

    def train(self) -> None:
        """Capture the current draft/seed before retained background training starts."""

        def action() -> None:
            text, seed = self._text(), int(self.seed.get())
            self.run(lambda: self.workspace.train(text, seed))

        self.guarded(action)

    def refresh_models(self) -> None:
        """Render true registry state while preserving an existing selected identity."""
        selection = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        for row in self.workspace.models():
            metrics = row["metrics"]
            self.tree.insert(
                "",
                "end",
                iid=row["model_id"],
                text=row["model_id"],
                values=(
                    row["algorithm"],
                    row["status"],
                    round(metrics["roc_auc"], 4),
                    round(metrics["brier"], 4),
                ),
            )
        if selection and self.tree.exists(selection[0]):
            self.tree.selection_set(selection[0])

    def show_evidence(self, value: Any) -> None:
        """Retain an explicit result for inspection/export and switch to its evidence panel."""
        self.last_evidence = value
        self._replace(self.evidence, json.dumps(value, indent=2, sort_keys=True, allow_nan=False))
        self.tabs.select(self.evidence_tab)

    def review(self) -> None:
        """Capture and verify the selected immutable model bundle without a deployment mutation."""

        def action() -> None:
            model = self._selected()
            self.run(lambda: self.workspace.review(model))

        self.guarded(action)

    def promote(self) -> None:
        """Require a real confirmation and an independently reverified model before promotion."""

        def action() -> None:
            model, reason = self._selected(), self.reason.get()
            if messagebox.askyesno(
                "Promote selected model?",
                (
                    "Verify recorded quality/provenance and replace this local champion? "
                    "This is an explicit operator decision, not fresh performance certification."
                ),
                parent=self.root,
            ):
                self.run(lambda: self.workspace.promote(model, reason))

        self.guarded(action)

    def challenger(self) -> None:
        """Capture a validated target and traffic value for real shadow/canary routing."""

        def action() -> None:
            model, traffic = self._selected(), int(self.traffic.get())
            self.run(lambda: self.workspace.challenger(model, traffic))

        self.guarded(action)

    def rollback(self) -> None:
        """Ask explicitly before restoring the real prior champion from audited history."""
        reason = self.reason.get()
        if messagebox.askyesno(
            "Rollback local champion?",
            (
                "Restore the actual prior champion from local audited history? "
                "Missing history is an error; no model is invented."
            ),
            parent=self.root,
        ):
            self.run(lambda: {"rolled_back_model": self.workspace.rollback(reason)})

    def sample(self) -> None:
        """Copy only observation fields from the first validated row into the inference editor."""

        def action() -> None:
            value = parse_dataset(self._text())[0].model_dump(
                mode="json", exclude={"row_id", "service_failure_24h"}
            )
            self._replace(self.observation, json.dumps(value, indent=2))

        self.guarded(action)

    def predict(self) -> None:
        """Capture the edited observation before running the original model-serving logic."""
        text = self.observation.get("1.0", "end-1c")
        self.run(lambda: self.workspace.predict(text))

    def drift(self) -> None:
        """Capture dataset/model context for read-only actual PSI calculation."""

        def action() -> None:
            model, text = self._selected(), self._text()
            self.run(lambda: self.workspace.drift(model, text))

        self.guarded(action)

    def export(self) -> None:
        """Write retained evidence only to a new user-selected JSON destination."""

        def action() -> None:
            if self.last_evidence is None:
                raise ValueError("Generate evidence first")
            path = filedialog.asksaveasfilename(
                parent=self.root, title="Export to a NEW JSON file", defaultextension=".json"
            )
            if path:
                export_new(Path(path), self.last_evidence)
                self.status.set("Evidence exported; existing files are never overwritten.")

        self.guarded(action)

    def close(self) -> None:
        """Retain active work and ownership until real completion, without force-
        kill."""
        if self.closing:
            return
        if not messagebox.askyesno(
            "Quit application?",
            (
                "Save the profile and stop? Active training must finish "
                "before this application closes."
            ),
            parent=self.root,
        ):
            return
        self.closing = True
        self.quit_button.configure(state="disabled")
        if self.busy:
            self.status.set(
                "Waiting for the real local operation to finish before releasing this profile…"
            )
        else:
            self._finish_close()

    def _finish_close(self) -> None:
        """Release completed work's profile ownership and destroy this owned window."""
        self.workspace.close()
        self.closed = True
        self.root.destroy()

"""File: config.py
Purpose: Load explicit runtime settings from environment variables without hidden global mutation.
Symbols and line locations: see docs/code-index.md; Settings owns registry, artifact, and
admin configuration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    """Immutable filesystem and authorization settings for one API process."""

    registry_path: Path
    artifact_root: Path
    admin_token: str | None

    @classmethod
    def from_environment(cls) -> Settings:
        """Build settings from documented variables with safe local defaults."""

        admin_token = os.getenv("OBSERVATORY_ADMIN_TOKEN")
        return cls(
            registry_path=Path(
                os.getenv("OBSERVATORY_REGISTRY_PATH", ".artifacts/registry.sqlite3")
            ),
            artifact_root=Path(os.getenv("OBSERVATORY_ARTIFACT_ROOT", ".artifacts/models")),
            admin_token=admin_token if admin_token else None,
        )

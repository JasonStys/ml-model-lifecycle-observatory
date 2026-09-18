"""File: validate-manifests.py
Purpose: Parse Kubernetes manifests and enforce the deployment's critical safety fields.
Symbols and line locations: see docs/code-index.md; main validates every YAML document.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).parents[1]


def _documents() -> list[dict[str, Any]]:
    """Load every Kubernetes object from the checked-in manifest set."""

    documents: list[dict[str, Any]] = []
    for path in sorted((ROOT / "deploy" / "kubernetes").glob("*.yaml")):
        documents.extend(document for document in yaml.safe_load_all(path.read_text()) if document)
    return documents


def main() -> None:
    """Reject missing objects, mutable tags, absent probes, or privileged execution."""

    documents = _documents()
    kinds = {document["kind"] for document in documents}
    if not {"Deployment", "Service"}.issubset(kinds):
        raise ValueError("Kubernetes manifests require a Deployment and Service")
    deployment = next(document for document in documents if document["kind"] == "Deployment")
    pod_spec = deployment["spec"]["template"]["spec"]
    container = pod_spec["containers"][0]
    if container["image"].endswith(":latest"):
        raise ValueError("mutable latest image tag is prohibited")
    for probe in ("startupProbe", "livenessProbe", "readinessProbe"):
        if probe not in container:
            raise ValueError(f"missing {probe}")
    security = container["securityContext"]
    if not security["runAsNonRoot"] or not security["readOnlyRootFilesystem"]:
        raise ValueError("container must be non-root with a read-only filesystem")
    if security["allowPrivilegeEscalation"]:
        raise ValueError("privilege escalation must be disabled")
    print(f"Validated {len(documents)} Kubernetes objects.")


if __name__ == "__main__":
    main()

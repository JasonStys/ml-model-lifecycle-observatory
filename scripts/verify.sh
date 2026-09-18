#!/usr/bin/env bash
# File: verify.sh
# Purpose: Run the complete deterministic local quality gate and evidence benchmark.
# Commands and variables: see docs/code-index.md; ROOT_DIR and PYTHON_BIN locate the checkout.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"

cd "${ROOT_DIR}"
"${PYTHON_BIN}" -m ruff format --check src tests
"${PYTHON_BIN}" -m ruff check src tests
"${PYTHON_BIN}" -m mypy
"${PYTHON_BIN}" -m pytest -m "not postgres"
"${PYTHON_BIN}" -m pip_audit --strict --disable-pip --no-deps \
  --cache-dir "${ROOT_DIR}/.pip-audit-cache" --progress-spinner off \
  --requirement requirements.lock
"${PYTHON_BIN}" -m ml_observatory.cli benchmark \
  --report docs/reports/generated/benchmark.json
node scripts/validate-repository.mjs
node scripts/generate-code-index.mjs --check
"${PYTHON_BIN}" scripts/validate-manifests.py
docker compose config --quiet

#!/usr/bin/env bash
# File: demo.sh
# Purpose: Build a fresh local lifecycle workspace and print a reviewable registry snapshot.
# Commands and variables: see docs/code-index.md; ROOT_DIR and WORKSPACE control output location.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE="${1:-${ROOT_DIR}/.artifacts/demo}"
PYTHON_BIN="${PYTHON_BIN:-python}"

cd "${ROOT_DIR}"
"${PYTHON_BIN}" -m ml_observatory.cli demo --workspace "${WORKSPACE}" --count 1200
"${PYTHON_BIN}" -m ml_observatory.cli inspect \
  --registry "${WORKSPACE}/registry.sqlite3"

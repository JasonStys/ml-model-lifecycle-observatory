# Contributing

## Development contract

Use Python 3.12–3.14, install `requirements.lock`, then install this package editable with
`--no-deps`. Keep changes deterministic, narrowly scoped, and supported by tests. Never commit
secrets, production telemetry, personal data, serialized executable objects, or generated runtime
artifacts.

All authored Python, SQL, shell, and JavaScript files require a header describing the file and its
purpose. Public behavior needs a docstring or nearby explanation. `docs/code-index.md` provides
exact declaration locations and must be regenerated after source changes.

## Required checks

```bash
python -m ruff format src tests scripts/validate-manifests.py
python -m ruff check src tests scripts/validate-manifests.py
python -m mypy
python -m pytest -m "not postgres"
python scripts/validate-manifests.py
node scripts/generate-code-index.mjs
node scripts/validate-repository.mjs
node scripts/generate-code-index.mjs --check
```

Use `bash scripts/verify.sh` when Docker is available to include the dependency audit, benchmark,
and Compose validation. A behavioral change must update the related document and report.

## Pull requests

Explain the problem, chosen approach, evidence, operational impact, and rollback. Keep promotion
gates strict. A model-quality regression, new unsafe artifact format, reduced test coverage, broken
auditability, or bypassed input validation is not acceptable without a reviewed design decision.

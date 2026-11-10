# Documentation refresh — 2026-11-09

By Jason Stys.

This documentation-only edition describes source `e3f47233539d2af763b5c30a2575e6544a0ba5d7`. It does not change application behavior, accounts, private data, installers or published releases.

## Published editions and completed review

| File | Bytes | SHA-256 | Reviewed scope |
| --- | ---: | --- | --- |
| [project-guide.docx](project-guide.docx) | 44821 | `5d95645c7968979de5403eb0b1abd588036ca6aa1c69c71f31ae5acbbb36cf76` | 5 pages, each viewed individually |

Word review checked plain black titles, readable pagination, whole table rows, source references, practical limits and absence of clipping or overflow. Render receipts were matched to the current DOCX digest before approval.

## Evidence and change boundary

- Functional baseline: `e3f47233539d2af763b5c30a2575e6544a0ba5d7`.
- Workflow observation: `2026-11-10T05:25:40.628667+00:00`; exact run URLs and source identities remain in [publications.json](publications.json).
- Local document-package validation verifies exact copied bytes, Office ZIP integrity, approved page/tab identities and internal documentation links. Repository-specific documentation and source-policy commands are run separately and recorded in the integration handoff.
- Source/index metadata is regenerated using the repository’s existing tools. Existing privacy, security, coverage and workflow gates are retained.
- PR and later main workflows must pass independently. This record does not claim future or unrun integration CI success.

## Interpretation

The Word files document the cited source; dated source reports retain their original execution scope. A passing workflow is distinct from completed analysis with zero findings, and neither establishes production suitability. Checksums identify exact bytes, not a signature or publisher attestation.

Use the [handbook](../handbook.md) to choose usage, design, security and test documentation. Keep editable Markdown and reviewed editions together; do not replace historical measurements with undated claims.

## Actual integration validation

59 platform-neutral Python tests passed with 97.16% combined coverage (95% floor), Ruff/format, strict mypy over 17 source files, repository links/headers, exact code index and two Kubernetes manifest contracts. The PostgreSQL-specific case remains a separate real hosted gate, not a locally passed test. Fresh isolated pytest directory used without altering the existing temp tree.

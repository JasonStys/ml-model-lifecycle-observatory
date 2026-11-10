# ML Model Lifecycle Observatory handbook

By Jason Stys.

Build authenticated read-only release dossiers with verified bundle/registry agreement, recorded quality gates, bounded history and matching drift context. Fixed SQLite handle leaks.

Build authenticated read-only release dossiers with verified bundle/registry agreement, recorded quality gates, bounded history and matching drift context. Fixed SQLite handle leaks.

Gives model reviewers explicit evidence and uncertainty before an independent promotion or rollback decision.

## Read the documentation

| Edition | Audience and contents |
| --- | --- |
| [project-guide.docx](reports/project-guide.docx) | User and developer guide: purpose, current usage, design, boundaries and source references. |

The editable Markdown remains the maintenance source. The Word files are readable editions. See [publication identities and review](reports/publications.json) and the [documentation refresh record](reports/documentation-refresh-2026-11-09.md).

## Current usage and help

[README quick start](../README.md) is the entry point. Use the project-specific guides below before changing inputs, operating modes or deployment assumptions.

### Usage and operations

- [operations](operations.md)
- [release review](release-review.md)

### Design and contracts

- [adr/0001 portable artifacts and small registry](adr/0001-portable-artifacts-and-small-registry.md)
- [api](api.md)
- [architecture](architecture.md)
- [complexity](complexity.md)
- [data contract](data-contract.md)
- [model lifecycle](model-lifecycle.md)
- [research](research.md)

### Security and validation

- [testing](testing.md)

## Historical results and reproduction

The reviewed source is [`e3f47233539d2af763b5c30a2575e6544a0ba5d7`](https://github.com/JasonStys/ml-model-lifecycle-observatory/tree/e3f47233539d2af763b5c30a2575e6544a0ba5d7). The observed functional workflow baseline is `e3f47233539d2af763b5c30a2575e6544a0ba5d7`; those observations are recorded at `2026-11-10T05:25:40.628667+00:00`. They do not certify an unrun later revision.

- [Detailed recorded validation](reports/practical-workflows-20261109.md)
- [Current Actions](https://github.com/JasonStys/ml-model-lifecycle-observatory/actions) records later integration checks separately.
- Preserve dated measurements and follow the existing testing guide to reproduce them; a test-source inventory alone does not establish execution.

## Practical boundaries

- Synthetic controlled operator-token lab, not multi-user production model-release authority.
- Dossiers verify bundle/registry metadata; they do not reread all raw dataset bytes or independently rerun recorded evaluations.
- No promotion/rollback occurs; history is capped at 100 entries with truncation explicit, and previous rollback candidates remain unverified.
- The 100-sample drift heuristic is not statistical confidence and the captured snapshot can become stale.

## Maintaining these editions

Update the editable usage/design/test documents first. Rebuild and visually review every Word page and workbook tab before replacing an edition; verify the exact binary digests and evidence source in publications.json. Keep account data, logs with secrets, installed-app state and private test stores out of documentation. Source and release assets retain their existing security and licensing boundaries.

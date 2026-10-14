# Portfolio synchronization — 2026-10-14

Created by Jason Stys.

This candidate combines the reviewed proposals below while preserving their
commit ancestry and the existing main-branch security fixes. Conflicting
version declarations are combined explicitly; affected locks are regenerated
from the reviewed manifests. No audit or coverage budget is lowered.

- [Original proposal #6](https://github.com/JasonStys/ml-model-lifecycle-observatory/pull/6).
- [Original proposal #9](https://github.com/JasonStys/ml-model-lifecycle-observatory/pull/9).
- [Original proposal #10](https://github.com/JasonStys/ml-model-lifecycle-observatory/pull/10).
- [Original proposal #11](https://github.com/JasonStys/ml-model-lifecycle-observatory/pull/11).
- [Original proposal #12](https://github.com/JasonStys/ml-model-lifecycle-observatory/pull/12).

Coordinated CodeQL steps use the same reviewed immutable release where present.
Source and generated-symbol contracts remain enforced by the existing workflows.
The complete candidate must pass its applicable native CI before promotion.
[Inspect candidate checks](https://github.com/JasonStys/ml-model-lifecycle-observatory/actions?query=branch%3Amaintenance%2Fportfolio-sync-20261014).

This maintenance does not add production deployments, user-data access, automatic
source promotion or new guarantees of security. Existing release tags and assets
are retained. Platform and model-quality limitations remain in the project README.

Python image proposal #8 is not included: its 3.15 release-candidate
runtime fails this package's declared `>=3.12,<3.15` support contract. Supporting
that runtime requires a separate dependency-wheel and runtime-port validation.

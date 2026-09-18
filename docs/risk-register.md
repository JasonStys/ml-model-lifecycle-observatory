# Risk register

This register uses NIST AI RMF's Govern, Map, Measure, and Manage functions as a practical
organizing frame. It is an educational project record, not a compliance claim.

| Function | Risk | Implemented control | Residual risk / production owner |
|---|---|---|---|
| Govern | Unaccountable release | reasoned promotion/rollback audit events; ADR and model card | require named approvers and change system — product/ML owner |
| Govern | Dependency compromise | exact lock, pinned actions, audit, CodeQL, Dependabot | sign releases/SBOM and enforce provenance — platform security |
| Map | Misuse beyond synthetic service health | intended/prohibited uses and prominent limitation | downstream users may ignore docs — product owner |
| Map | Invalid or sensitive telemetry | strict contract; no raw features in prediction log | source privacy/quality not solved — data owner/privacy |
| Measure | Leakage or optimistic evaluation | disjoint train/calibration/test partitions | temporal and organizational leakage need domain data — ML owner |
| Measure | Poor calibration | Brier, log loss, ECE, sigmoid calibration | metrics can drift after deployment — ML owner |
| Measure | Uneven behavior | recall by synthetic region/tier and maximum-gap gate | synthetic groups are not a fairness assessment — responsible AI owner |
| Measure | Input drift | per-feature PSI with sample size and fixed thresholds | PSI does not explain causes or label shift — SRE/data owner |
| Manage | Unsafe artifact | canonical JSON, digest/path/schema/shape/finite checks | file-system compromise still matters — platform owner |
| Manage | Bad canary | stable bounded routing and shadow evidence | no automatic statistical stopping — release owner |
| Manage | Registry corruption/contention | transactions, constraints, WAL, concurrent tests | SQLite cannot provide distributed coordination — database owner |
| Manage | Failed rollback | immutable history and tested prior-champion restore | schema/data incompatibility can remain — incident commander |
| Manage | Unauthorized mutation | explicit admin token and constant-time compare | shared-token demo lacks identity/roles/rotation — security owner |
| Manage | Over-trust in prediction | abstention and no autonomous action | consumers may still over-automate — product owner |

## Release decision minimum

Before any real adaptation, define accountable owners, data rights and retention, representative
validation, user impact, security threat model, monitoring objectives, escalation paths, rollback
compatibility, and independent approval. Replace synthetic thresholds with domain-reviewed ones and
test the complete socio-technical workflow—not only the model.

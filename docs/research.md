# Research and engineering basis

Sources were reviewed on 2026-09-17. Primary documentation and standards are preferred. The
repository implements a deliberately bounded subset and records where production work remains.

## Calibration and evaluation

Scikit-learn documents sigmoid and isotonic calibration through `CalibratedClassifierCV` and notes
that calibration data should be disjoint from estimator fitting. This implementation uses a
separate calibration partition and a transparent one-dimensional sigmoid fit, then reports Brier
score, log loss, expected calibration error, discrimination, threshold metrics, and abstention.

- [Scikit-learn: CalibratedClassifierCV](https://scikit-learn.org/stable/modules/generated/sklearn.calibration.CalibratedClassifierCV.html)
- [Scikit-learn: probability calibration](https://scikit-learn.org/stable/modules/calibration.html)

## Artifact safety

Scikit-learn's persistence guide warns that pickle-based formats can execute arbitrary code when
loaded and require compatible dependency environments. Because the included estimators are small,
the project chooses validated numeric JSON instead of executable serialization and records exact
dependency versions as provenance.

- [Scikit-learn: model persistence](https://scikit-learn.org/dev/model_persistence.html)

## Health semantics and process model

Kubernetes distinguishes startup, liveness, and readiness probes. The deployment uses all three:
startup/liveness verify the process, while readiness requires a champion. FastAPI's deployment
guidance explains worker processes; this repository documents that SQLite constrains the demo to
one writer and does not claim safe multi-worker coordination.

- [Kubernetes: liveness, readiness, and startup probes](https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/)
- [FastAPI: server workers](https://fastapi.tiangolo.com/deployment/server-workers/)

## AI risk framing

The NIST AI Risk Management Framework Core organizes work into Govern, Map, Measure, and Manage.
The project maps that framing to ownership and scope, synthetic-data/model context, measurable
quality/drift/subgroup evidence, and controlled promotion/rollback. This is alignment for an
educational implementation, not a certification or complete organizational risk program.

- [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework)
- [NIST AI RMF Core](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/)

## Version selection

The lock file records an exact install, while `pyproject.toml` gives narrow compatible ranges.
Current published package metadata was checked before implementation; CI installs only the lock.

- [PyPI: scikit-learn](https://pypi.org/project/scikit-learn/)
- [PyPI: FastAPI](https://pypi.org/project/fastapi/)

## Local design conclusions

- Favor inspectable evidence and explicit state transitions over a heavy platform for this scope.
- Keep train, calibration, and test decisions separate.
- Treat artifact loading, operator mutation, and external requests as trust boundaries.
- Keep monitoring advisory; require accountable review for promotion and rollback.
- State limitations prominently and avoid generalizing synthetic performance to production.

# Model lifecycle

## 1. Generate and validate

Create deterministic synthetic observations, validate every record, serialize canonical JSONL,
compute its SHA-256 digest, and write metadata. The dataset digest follows each candidate.

## 2. Split before decisions

Stratify the dataset into training, calibration, and locked-test partitions. Fit the standardizer
and estimator only on training. Fit the sigmoid calibration layer and choose the F2-optimized
threshold on calibration. Measure final quality only on test.

## 3. Compare evidence

Train a regularized logistic regression and a compact single-hidden-layer MLP. Report ROC AUC,
Brier score, log loss, accuracy, precision, recall, F1, expected calibration error, abstention
coverage/selective accuracy, and recall by synthetic region/tier. Candidates must reach ROC AUC
0.68 and keep maximum subgroup recall gap at or below 0.40. The eligible candidate with the lowest
Brier score wins; ties are deterministic.

## 4. Package safely

Convert only required numeric parameters into schema-versioned canonical JSON. Include input order,
standardization, calibration, decision policy, reference histograms, dependency versions, and data
digest. Content-address the document and verify it before every load. Python object deserialization
is not part of the runtime.

## 5. Register and promote

Registration is idempotent by artifact digest. Promotion atomically retires the current champion,
sets the target champion, clears any challenger, and appends history/audit records. There is always
at most one active champion and one active challenger.

## 6. Observe challenger behavior

A challenger may receive 0% traffic for shadow output or 1–50% deterministic canary traffic. A
SHA-256 bucket of `request_id` produces stable assignment across processes. Both model outputs are
recorded when a challenger is present, but raw feature vectors are not.

## 7. Monitor and respond

Reference training histograms travel with the artifact. PSI compares a current batch against those
distributions: values below 0.10 are stable, 0.10–0.25 warning, and at least 0.25 critical. Drift is
a signal, not an automatic causal diagnosis or autonomous rollout trigger.

## 8. Roll back

Rollback selects the most recent distinct prior champion from deployment history and routes it
through the same promotion transaction. The reason and resulting state remain auditable. See the
[operations runbook](operations.md).

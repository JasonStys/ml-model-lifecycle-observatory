# Complexity and performance

Let `n` be records, `d=8` numeric features, `b=10` histogram bins, `m` MLP hidden units, `k` models,
and `h` deployment-history rows. `d`, `b`, and the included network dimensions are bounded.

| Operation | Time | Additional space | Notes |
|---|---:|---:|---|
| Generate/validate dataset | O(n·d) | O(n·d) | materialized for deterministic splitting |
| Stratified split | O(n) expected | O(n) | shuffle/index work per class |
| Logistic training | iterative O(i·n·d) | O(n·d) | solver iterations depend on convergence |
| Compact MLP training | iterative O(i·n·d·m) | O(n·m + d·m) | intentionally small single hidden layer |
| Evaluation/subgroups | O(n·d) | O(n + groups) | probability and group scans |
| Reference histograms | O(n·d·log b) | O(d·b) | NumPy binning; `b` is fixed |
| Artifact write/load | O(a) | O(a) | `a` is JSON artifact bytes; digest included |
| Register/promote | O(log k) plus transaction | O(1) | indexed identity/status lookups |
| Rollback target lookup | O(h) | O(1) | recent history scan; small demo table |
| One prediction | O(d) logistic; O(d·m) MLP | O(d+m) | pure NumPy runtime |
| Canary routing | O(r) | O(1) | `r` request-ID bytes hashed |
| PSI monitoring | O(n·d·log b) | O(d·b) | batch matrix plus fixed reference bins |

The CLI benchmark trains both candidates on 800 records and runs 5,000 portable-model predictions.
The enforced ceilings are 30 seconds total training and 5 ms p95 per in-process prediction. These
budgets detect major regressions but are not production capacity claims; see
[benchmark.md](reports/benchmark.md).

For large datasets, replace full materialization with versioned columnar storage and explicit
streaming/batch evaluation. For high-throughput serving, cache verified immutable models, use a
network registry rather than SQLite, measure end-to-end latency, and load-test concurrency under
representative resources.

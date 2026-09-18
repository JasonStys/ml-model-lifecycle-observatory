# Performance benchmark

The benchmark trains both candidates on 800 deterministic records, selects and writes the winning
portable artifact, reloads it through the integrity boundary, and executes 5,000 predictions.

| Budget | Enforced ceiling |
|---|---:|
| Total candidate training | 30 seconds |
| In-process p95 portable inference | 5 milliseconds |

The recorded local Windows/CPython 3.12.14 run on 2026-09-17 completed candidate training in
**1.381 seconds** and measured **0.0156 ms p95** across 5,000 predictions. Both checks passed. The
numbers are evidence for that host and revision, not universal performance claims.

Run:

```bash
python -m ml_observatory benchmark --report docs/reports/generated/benchmark.json
```

The command exits nonzero when a budget is exceeded. Exact timing is host-dependent, so generated
JSON is not committed; CI uploads the result with the commit's coverage evidence. Budgets are
regression tripwires, not throughput or service-level claims. Network, queueing, serialization,
concurrency, cold starts, and downstream storage are outside this microbenchmark.

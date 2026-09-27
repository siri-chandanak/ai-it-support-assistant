# Performance Budgets

## Purpose

These values are initial engineering benchmark budgets used for
development, staging, and performance-regression testing.

They are not production SLOs.

A production SLO is a long-term operational reliability objective.

A benchmark budget is a threshold used during controlled performance
testing to detect regressions and identify capacity limits.

## Initial Budgets

| Metric | Initial Budget |
|---|---:|
| Lightweight API read p95 | < 500 ms |
| RAG answer p95 | < 3,000 ms |
| Qdrant search p95 | < 200 ms |
| OPA decision p95 | < 100 ms |
| Worker queue delay p95 | < 10,000 ms |
| HTTP error rate | < 1% |
| Unauthorized false allows | 0 |

## Security Invariant

Performance testing must never improve benchmark results by disabling
security controls.

The following optimizations are prohibited:

- removing authorization filters
- bypassing OPA
- skipping worker reauthorization
- disabling audit logging
- bypassing human approval
- caching authorization decisions indefinitely

Unauthorized false allows must always remain zero.

## Regression Guidance

Initial regression thresholds:

- RAG p95 should not regress by more than 25%
- OPA p95 should not regress by more than 50%
- HTTP error rate should remain below 1%
- unauthorized false allows must remain zero

These thresholds should be updated after stable staging baselines have
been collected.

## Stress-Test Stop Conditions

Stop increasing load when any of the following occurs:

- HTTP error rate exceeds 5%
- p95 latency exceeds 2x its benchmark budget
- PostgreSQL connection pool becomes exhausted
- application memory approaches its configured limit
- worker queue grows continuously without recovering
- downstream dependency saturation becomes unsafe
- security behavior changes under load

## Review

These budgets must be revisited after meaningful staging measurements
are available.

Do not derive production capacity from local laptop benchmarks.
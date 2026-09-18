# Observability SLOs

This document defines the initial Service Level Indicators (SLIs),
Service Level Objectives (SLOs), error budgets, and alerting guidance
for the AI IT Support Assistant platform.

These values are initial internal engineering targets.

They are not external customer commitments and should be adjusted after
real production telemetry is available.

---

## 1. API Availability

### SLI

Percentage of valid API requests completed without unexpected server
failure.

Expected client errors such as authentication failures, authorization
denials, and invalid requests are not counted as platform availability
failures.

### Initial SLO

99.9% availability over a rolling 30-day window.

### Failure Examples

- HTTP 5xx response
- unhandled exception
- required dependency unavailable
- unexpected database failure

---

## 2. RAG Latency

### SLI

End-to-end duration of successful RAG requests.

This includes:

- query embedding
- Qdrant retrieval
- retrieval filtering
- LLM generation

### Initial SLO

p95 successful RAG request latency < 3 seconds.

Correct retrieval or sufficiency abstentions are not system failures.

---

## 3. Policy Decision Point Availability

### SLI

Percentage of authorization evaluations successfully completed by the
configured PDP.

### Initial SLO

99.99% PDP availability.

### Latency Targets

Local PDP:

p95 < 20 ms

External OPA:

p95 < 100 ms

A valid policy DENY is a successful PDP operation.

OPA timeout, connectivity failure, or invalid response is a PDP
technical failure.

---

## 4. Worker Queue Delay

### SLI

Time between an action becoming approved and a worker successfully
claiming it.

Calculated as:

`execution_started_at - approved_at`

### Initial SLO

p95 queue delay < 10 seconds.

---

## 5. Deployment Restart Rollout

### SLI

Percentage of approved deployment restart actions that successfully
reach the expected healthy rollout state within the configured timeout.

### Initial SLO

99% of valid restart actions complete successfully within the configured
rollout timeout.

For development, the rollout timeout may initially be approximately
2 minutes.

---

## 6. Security Objectives

Security objectives are stricter than ordinary reliability objectives.

### False Authorization Allows

Target:

0

An unauthorized operation being incorrectly allowed is a critical
security failure.

### Unauthorized Document Leakage

Target:

0

A user must never receive document content outside their authorized
scope.

---

## 7. Error Budgets

An error budget represents the amount of unreliability allowed by an
SLO.

For example:

SLO:

99.9%

Error budget:

100% - 99.9% = 0.1%

The error budget can be used when deciding whether engineering effort
should prioritize:

- new features
- reliability improvements
- incident remediation
- capacity improvements

Security objectives such as false authorization allows have a target of
zero and therefore should not be treated like normal availability error
budgets.

---

## 8. Initial Alert Recommendations

These are initial recommendations and may be adjusted after production
baselines are available.

### API

Alert when:

HTTP 5xx rate > 2% for 5 minutes.

### OPA / Authorization

Alert when:

authorization service is unavailable for more than 1 minute.

### Worker

Alert when:

approved action queue depth > 20 for 10 minutes.

### Kubernetes Actions

Alert when:

more than 3 rollout failures occur within 15 minutes.

### Security

A confirmed false authorization allow should be treated as a
high-severity security event.

Policy and security evaluation pipelines should fail when false allows
are detected.

---

## 9. SLO Review

Initial SLOs must be reviewed after sufficient production data exists.

The team should examine:

- p50 latency
- p95 latency
- p99 latency
- error rates
- queue delay
- OPA latency
- rollout duration
- dependency failures

Targets should be changed based on measured system behavior rather than
arbitrary tightening.
# Platform Observability

The AI IT Support Assistant uses OpenTelemetry, Prometheus, structured
logging, and durable audit events to provide end-to-end operational
visibility.

Observability has four major signals:

1. Traces
2. Metrics
3. Logs
4. Audit events

Each serves a different purpose.

---

## Service Names

The platform uses different OpenTelemetry service names for different
runtime processes.

API:

`ai-it-support-api`

Worker:

`ai-it-support-worker`

MCP:

`ai-it-support-mcp`

The deployment environment is also attached to telemetry.

Examples:

- development
- staging
- production

---

## Request ID and Trace ID

The existing application `request_id` remains in use.

OpenTelemetry additionally provides:

- `trace_id`
- `span_id`

These identifiers have different purposes.

### Request ID

Application-level correlation identifier associated with an incoming
request.

### Trace ID

Distributed tracing identifier used to correlate work across
instrumented services and dependencies.

Both are retained.

A trace ID must never be treated as authentication or authorization
identity.

---

## Important Traces and Spans

### API

FastAPI requests are automatically instrumented.

### Database

SQLAlchemy operations against PostgreSQL are automatically
instrumented.

### Outbound HTTP

HTTPX operations such as external OPA requests are automatically
instrumented.

### Agent

Important span:

`agent.route`

### RAG

Typical hierarchy:

`rag.answer`

- `embedding.encode`
- `rag.retrieve`
- `qdrant.query`
- `rag.filter`
- `llm.generate`

### Policy

Important span:

`policy.evaluate`

A valid authorization DENY is expected business behavior and must not
be classified as an infrastructure error.

OPA timeout, connection failure, or malformed response is a technical
failure.

### Worker

Important spans include:

- `worker.action.execute`
- `worker.reconcile_action`

### Kubernetes

Important spans include:

- `kubernetes.read`
- `kubernetes.restart`
- `kubernetes.verify_restart`
- `kubernetes.rollout.monitor`

Rollout polling should use span events rather than generating a child
span for every polling iteration.

---

## Asynchronous Action Correlation

An API proposal and worker execution are separate asynchronous units of
work.

The pending action stores:

- `origin_request_id`
- `origin_trace_id`

Worker execution starts its own trace and correlates back to the
originating request.

The worker trace must not pretend to be a continuously active HTTP
child span.

A future implementation may use OpenTelemetry Span Links for stronger
causal correlation.

---

## Prometheus Metrics

The platform exposes operational metrics for:

### HTTP

- request count
- request latency

### RAG

- retrieval requests
- retrieval failures
- retrieved chunks
- retrieval latency
- abstentions
- end-to-end RAG latency

### LLM

- requests
- failures
- latency
- input token count
- output token count

### Agent

- requests
- route distribution
- routing failures
- duration

### Authorization

- policy decisions
- policy denials
- policy failures
- policy latency
- OPA requests
- OPA failures
- OPA timeouts
- OPA latency

### Approvals

- action proposals
- approvals
- rejections

### Worker

- claimed actions
- successful actions
- failed actions
- stale action recovery
- claim conflicts
- queue depth
- queue delay
- action execution duration

### Kubernetes

- read operations
- write attempts
- write failures
- restart latency
- rollout failures
- rollout timeouts

### Cache

- embedding cache hits
- embedding cache misses
- retrieval cache hits
- retrieval cache misses

### MCP

- tool calls
- tool denials
- tool duration
- resource reads

---

## Metric Cardinality Rules

Prometheus labels must contain bounded values.

Good examples:

- HTTP method
- route template
- status class
- action type
- controlled outcome
- controlled reason code
- PDP mode

Do not use the following as metric labels:

- username
- request ID
- trace ID
- approval ID
- incident ID
- arbitrary resource IDs
- raw URLs
- exception messages

Specific identifiers belong in logs, traces, or audit events rather
than Prometheus labels.

---

## Sensitive Telemetry Rules

The following values must never be emitted into telemetry:

- Authorization headers
- JWTs
- passwords
- API keys
- secrets
- kubeconfig contents
- raw document chunks
- full LLM prompts
- embedding vectors

Prefer explicit allowlists of safe attributes rather than copying
entire application objects into spans or logs.

---

## Logging Correlation

Operational logs should include:

- request ID
- trace ID
- span ID

when available.

Audit records remain separate from operational logging and tracing.

Tracing must never replace durable audit records.

---

## Trace Sampling

For local development and initial staging validation, the platform uses
100% trace sampling.

### Current Policy

- Development: 100%
- Staging: 100% during initial validation
- Production: determined after production telemetry baselines exist

High-risk actions should receive stronger trace retention where
appropriate.

Examples:

- `deployment.restart`
- `incident.create`
- policy errors
- authorization anomalies

Sampling must never affect authorization, audit persistence, or
application behavior.

---

## Recommended Dashboards

### API / RAG

- request rate
- 5xx rate
- HTTP p50 / p95 / p99 latency
- RAG p95
- LLM latency
- Qdrant latency
- RAG abstentions
- LLM failures

### Agent / Tools

- route distribution
- routing failures
- service-status calls
- Kubernetes reads
- incident proposals
- restart proposals

### Authorization

- policy decisions/sec
- allow / deny
- denials by reason
- OPA p95
- OPA timeout
- OPA errors
- bundle revision
- shadow mismatch

### Worker / Actions

- queue depth
- queue delay p95
- executing actions
- action success/failure
- stale recovery
- claim conflicts
- rollout duration
- rollout timeout

---

## SLOs

Detailed SLO definitions are maintained in:

`docs/observability-slos.md`

Initial objectives include:

- API availability: 99.9%
- successful RAG p95 latency: < 3 seconds
- PDP availability: 99.99%
- local PDP p95: < 20 ms
- external OPA p95: < 100 ms
- worker queue delay p95: < 10 seconds
- healthy restart rollout success: 99%
- false authorization allows: 0
- unauthorized document leaks: 0

---

## Alerting

Initial alert recommendations are documented in:

`docs/observability-slos.md`

Alerting should focus on user-impacting or safety-impacting symptoms.

---

## Local OpenTelemetry Collector

Collector configuration:

`observability/otel-collector.yaml`

Start the Collector before running the API with OpenTelemetry enabled.

Example:

```bash
docker run --rm \
  --name ai-support-otel-collector \
  -p 4317:4317 \
  -p 4318:4318 \
  -v "$(pwd)/observability/otel-collector.yaml:/etc/otelcol-contrib/config.yaml" \
  otel/opentelemetry-collector-contrib:latest \
  --config=/etc/otelcol-contrib/config.yaml
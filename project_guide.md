# AI IT Support Assistant — Engineering & Branch Guide

This document explains how the AI IT Support Assistant evolved from a basic API into a production-oriented GenAI and operations platform.

It is intended for engineers who want to understand:

- why the architecture is structured this way
- what each feature branch introduced
- how RAG, agents, security, tools, persistence, and operations fit together
- how protected actions are controlled
- how the project should continue evolving

---

## System Context

The platform sits between users, enterprise knowledge, and operational systems.

```text
                           User / Frontend
                                  │
                                  ▼
                            FastAPI Backend
                                  │
             ┌────────────────────┼────────────────────┐
             │                    │                    │
             ▼                    ▼                    ▼
        Authentication       Authorization        Agent Router
                                                       │
                              ┌────────────────────────┴───────────────────┐
                              │                                            │
                              ▼                                            ▼
                           RAG Engine                                  Live Tools
                              │                                            │
                  ┌───────────┴───────────┐                     ┌──────────┴──────────┐
                  │                       │                     │                     │
               Qdrant                  Ollama                Kubernetes            MCP
                  │                                             │
                  ▼                                             ▼
           Enterprise Docs                              Controlled Actions
```

A key architectural rule is that model output never directly controls infrastructure.

Protected writes are mediated by application logic:

```text
Model / Agent
    │
    ▼
Proposed Action
    │
    ▼
Authorization
    │
    ▼
Persisted Action
    │
    ▼
Human Approval
    │
    ▼
Worker
    │
    ▼
External System
    │
    ▼
Verification
    │
    ▼
Audit
```

---

# Branch Model

`main` is the integration branch.

Feature work is developed in capability-specific branches and merged after validation.

Typical workflow:

```bash
git checkout main
git pull

git checkout -b feature/<capability>

# implement

uv run pytest
uv run ruff check .

git add .
git commit -m "Add <capability>"
git push -u origin feature/<capability>
```

---

# Feature Branch History

> The list below reflects the feature branches used or planned during development.  
> Because merged branches may be deleted from GitHub after pull requests are completed, use the Git commands near the end of this document to verify the current remote branch inventory.

| Branch | Area | Purpose |
|---|---|---|
| `main` | Platform Foundation | Integration branch containing the production-oriented backend. |
| `feature/configuration` | Configuration | Environment-based configuration and safe `.env` handling. |
| `feature/document-ingestion` | Ingestion | Document upload API and validation. |
| `feature/document-text-extraction` | Ingestion | Text extraction from uploaded files. |
| `feature/document-chunking` | RAG | Chunk creation, overlap, and source metadata. |
| `feature/vector-store` | RAG | Embeddings and Qdrant persistence. |
| `feature/retrieval` | RAG | Semantic retrieval with top-k and score thresholds. |
| `feature/rag-generation` | RAG | Grounded answer generation using retrieved evidence. |
| `feature/structured-rag` | RAG | Structured response schema, citations, and grounding metadata. |
| `feature/rag-evaluation` | Evaluation | Retrieval, grounding, citation, and abstention evaluation. |
| `feature/dependency-resilience` | Reliability | Timeouts, retries, backoff, and dependency failure handling. |
| `feature/observability` | Observability | Structured logs, request IDs, and latency measurements. |
| `feature/rag-cache` | Performance | Cache behavior with isolation and invalidation concerns. |
| `feature/auth-rag` | Security | Authentication and authorization-aware document retrieval. |
| `feature/auth-rag-evaluation` | Security | Data-leakage and unauthorized-retrieval testing. |
| `feature/agent-router` | Agent | Route requests between RAG and live tools. |
| `feature/agent-k8s-read` | Tools | Read-only Kubernetes access and routing evaluation. |
| `feature/incident-approval` | Actions | Controlled incident creation with approval. |
| `feature/persistent-approvals` | Actions | Persisted approvals, audit events, and idempotency. |
| `feature/action-state-machine` | Actions | Transactional action lifecycle and concurrency control. |
| `feature/k8s-restart` | Operations | Protected Kubernetes deployment restart. |
| `feature/rollout-verification` | Operations | Post-action rollout verification. |
| `feature/action-worker` | Workers | Durable background execution model. |
| `feature/postgres-alembic` | Persistence | PostgreSQL and Alembic-backed durable state. |
| `feature/mcp-server` | MCP | Controlled tool exposure through MCP. |
| `feature/production-identity` | Security | Fine-grained identity and resource permissions. |
| `feature/policy-layer` | Authorization | Central policy-decision abstraction. |
| `feature/policy-evaluation` | Authorization | Decision tracing and policy evaluation. |
| `feature/opa-pdp` | Authorization | External OPA policy decision point. |
| `feature/opa-policy-cicd` | Authorization | Policy bundles, testing, revisioning, and rollback. |
| `feature/platform-observability` | Observability | OpenTelemetry and Prometheus across platform workflows. |
| `feature/production-deployment` | Platform | Production deployment and CI/CD resources. |
| `feature/production-readiness` | Reliability | End-to-end readiness and failure testing. |
| `feature/performance-capacity` | Performance | Throughput, latency, saturation, and cost/capacity analysis. |
| `feature/async-ingestion` | Ingestion | Durable asynchronous ingestion architecture. |
| `feature/document-lifecycle` | Documents | Versioning, retirement, tombstones, and cleanup. |
| `feature/advanced-retrieval` | RAG | Hybrid retrieval, reranking, and query expansion. |
| `feature/graph-rag` | Graph RAG | Service dependency graph and vector/graph integration. |
| `feature/graph-sync` | Graph RAG | Kubernetes-to-graph reconciliation. |
| `feature/agent-planning` | Agent | Bounded multi-action investigations. |
| `feature/investigation-sessions` | Agent | Durable conversation and investigation sessions. |
| `feature/human-handoff` | HITL | Human escalation and structured handoff. |
| `feature/case-management` | Integrations | External case-management integration. |
| `feature/feedback-learning` | Evaluation | Feedback-driven evaluation dataset improvements. |
| `feature/llmops` | LLMOps | Prompt/model versioning, evaluation gates, canary, rollback. |
| `feature/secrets-identity-tls` | Security | Secret management, workload identity, TLS, and rotation. |
| `feature/threat-model-redteam` | Security | Threat modeling and adversarial regression. |
| `feature/multi-tenancy` | Platform | Tenant-aware isolation across data and execution. |
| `feature/disaster-recovery` | Resilience | Backup, restore, and continuity procedures. |
| `feature/sre-operations` | SRE | SLIs, SLOs, alerts, runbooks, and incident operations. |

---

# Application Foundation

The project starts with a conventional application architecture rather than placing all behavior in a single `main.py`.

The foundation includes:

- FastAPI application entrypoint
- installable Python package
- dependency management through `uv`
- configuration through Pydantic Settings
- automated tests
- linting
- GitHub Actions

This keeps infrastructure, AI, and domain logic replaceable and testable.

---

# Document Ingestion

The ingestion pipeline separates transport from processing.

```text
HTTP Upload
    │
    ▼
Validation
    │
    ▼
Text Extraction
    │
    ▼
Chunking
    │
    ▼
Metadata
    │
    ▼
Embedding / Indexing
```

This separation allows each layer to evolve independently.

Examples:

- upload validation can change without changing chunking
- chunking strategy can change without changing the API
- embeddings can change without changing document extraction

---

# RAG Architecture

The RAG path is split into explicit stages.

```text
User Query
    │
    ▼
Query Embedding
    │
    ▼
Qdrant Search
    │
    ▼
Filtered Evidence
    │
    ▼
LLM Generation
    │
    ▼
Structured Response
    │
    ▼
Citations
```

This makes it possible to evaluate retrieval separately from generation.

That distinction matters because a bad answer can be caused by:

```text
wrong evidence
```

or:

```text
correct evidence + poor generation
```

The project therefore keeps retrieval evaluation, generation validation, grounding checks, and citation validation separate.

---

# Authorization-Aware Retrieval

Enterprise retrieval cannot treat every document as globally visible.

The secure retrieval problem is:

```text
Find the most relevant chunks
that this specific user is allowed to access.
```

not simply:

```text
Find the most relevant chunks.
```

Authorization is therefore part of retrieval, caching, and evaluation.

Security tests should verify:

- unauthorized documents are not returned
- metadata does not expose protected information
- cache keys cannot cross security boundaries
- user/tenant context is preserved
- policy failures do not become implicit access

---

# Agent Architecture

The agent is a router and orchestrator, not an unrestricted autonomous process.

Example decisions:

```text
Knowledge question
      │
      ▼
     RAG
```

```text
Live infrastructure question
      │
      ▼
Kubernetes Tool
```

The application retains control over:

- allowed tools
- request validation
- authorization
- timeouts
- action boundaries
- persistence
- audit

---

# Read-Only Kubernetes Tooling

Read access is introduced before write access.

Typical information includes:

- deployment status
- replicas
- pods
- rollout state
- namespaces
- resource health

Read-only tooling provides operational value while minimizing risk.

---

# Controlled Write Architecture

Write operations require stronger guarantees.

The platform uses persisted state instead of one synchronous HTTP call.

Example lifecycle:

```text
PENDING
   │
   ▼
APPROVED
   │
   ▼
QUEUED
   │
   ▼
RUNNING
   │
   ▼
VERIFYING
   │
   ├──────► FAILED
   │
   ▼
SUCCEEDED
```

Possible terminal states may also include:

```text
REJECTED
CANCELLED
```

The exact state machine is enforced by application code rather than by model output.

---

# Idempotency

Protected writes are designed to avoid duplicate logical execution.

Example risk:

```text
Worker patches deployment
        │
        ▼
Worker crashes before DB update
        │
        ▼
Replacement worker sees incomplete state
```

Without idempotency and reconciliation, the operation might execute twice.

The worker therefore needs enough persisted context to determine whether to:

- execute
- retry
- resume verification
- stop

---

# Rollout Verification

An API-level success from Kubernetes does not guarantee an operationally healthy deployment.

The system verifies:

- updated replica availability
- rollout progress
- readiness
- failure conditions
- timeout conditions

This creates an important distinction:

```text
request accepted
```

versus:

```text
desired state achieved
```

---

# PostgreSQL Persistence

PostgreSQL stores durable business and operational state.

Current domains include:

- users
- resource permissions
- incidents
- pending actions
- audit events

Alembic migrations are used to evolve the schema safely.

Production releases should know both:

```text
application version
database migration version
```

---

# Policy Decision Architecture

Authorization logic is centralized behind a policy-decision layer.

A policy request can be represented as:

```json
{
  "subject": "user-123",
  "resource": "deployment/ai-support-api",
  "action": "restart",
  "context": {
    "environment": "production"
  }
}
```

The application consumes the decision without embedding every rule inside the endpoint.

This architecture allows a local policy implementation and an external OPA implementation to share the same application contract.

---

# OPA Integration

OPA serves as an external policy decision point.

The application remains responsible for:

- preparing policy input
- calling OPA
- interpreting the response
- failing safely
- recording decision metadata
- enforcing the result

OPA downtime must not become permission.

Protected operations should stop when authorization cannot be evaluated reliably.

---

# MCP Design

MCP provides a standardized interface for tools.

The important architectural rule is:

```text
MCP is another interface to controlled services.
```

It is not:

```text
a shortcut around authentication or authorization.
```

Every sensitive MCP-backed capability should preserve the same application guarantees as the HTTP/API path.

---

# Observability

A single user request may cross many components.

Example:

```text
HTTP
 │
 ▼
Authentication
 │
 ▼
Policy Decision
 │
 ▼
Agent
 │
 ▼
Qdrant
 │
 ▼
LLM
```

or:

```text
HTTP
 │
 ▼
Agent
 │
 ▼
Tool
 │
 ▼
Worker
 │
 ▼
Kubernetes
```

Operational debugging therefore requires correlation across components.

Useful telemetry includes:

- request ID
- trace ID
- route
- latency
- agent route
- tool name
- policy decision
- worker/action ID
- error category

Sensitive content should not be logged indiscriminately.

---

# Performance and Capacity Engineering

Performance work focuses on evidence.

Measurements include:

```text
API throughput
RAG response latency
Qdrant search latency
embedding throughput
LLM latency
DB pool pressure
worker throughput
queue delay
cache hit ratio
OPA latency
MCP throughput
```

Useful latency metrics include:

```text
p50
p95
p99
```

Capacity engineering converts those measurements into:

- scaling thresholds
- worker counts
- connection pool sizing
- request limits
- performance budgets
- cost estimates

---

# CI/CD Strategy

Pull requests should validate code before merge.

Typical pipeline:

```text
checkout
   │
   ▼
dependency install
   │
   ▼
lint
   │
   ▼
tests
   │
   ▼
RAG/security/policy evaluations
   │
   ▼
build validation
```

Production or staging workflows can additionally include:

- migrations
- Kubernetes readiness
- policy revision checks
- end-to-end tests
- safe smoke tests
- deployment metadata capture

---

# Production Readiness

A production-ready system needs evidence beyond "the API is running."

Examples:

```text
Git SHA
image digest
database migration revision
policy revision
readiness checks
security invariants
evaluation results
safe E2E results
```

Operational invariants should be automated wherever possible.

Examples:

```text
unauthorized document leaks = 0
false authorization allows = 0
duplicate logical writes = 0
```

---

# Planned Platform Extensions

The architecture is intentionally designed to continue into:

### Async Ingestion

```text
Upload
  │
  ▼
Job
  │
  ▼
Extract
  │
  ▼
Chunk
  │
  ▼
Embed
  │
  ▼
Index
```

### Document Lifecycle

- versions
- replacement
- retirement
- tombstones
- retention
- stale vector cleanup

### Advanced Retrieval

```text
keyword retrieval
       +
vector retrieval
       │
       ▼
candidate set
       │
       ▼
reranker
       │
       ▼
best evidence
```

### Graph RAG

Graph relationships can answer dependency-oriented questions that vector search alone handles poorly.

```text
checkout-service
      │
      ├── ai-support-api
      │      └── postgres
      │
      └── kafka
             └── order-consumer
```

### Durable Investigations

A bounded investigation can orchestrate multiple safe actions:

```text
retrieve runbook
      │
inspect deployment
      │
inspect pods
      │
inspect dependency graph
      │
produce recommendation
```

### Human Escalation

Escalation packages can contain:

- summary
- evidence
- tools executed
- actions attempted
- results
- recommended next action

### External Case Management

The integration layer can support systems such as:

- Jira
- ServiceNow

### LLMOps

Production model/prompt delivery should include:

- versioning
- evaluation gates
- canary rollout
- rollback
- provenance

### Security Hardening

Future production hardening includes:

- secret manager integration
- workload identity
- TLS
- key rotation
- threat modeling
- adversarial testing
- regression suites

### Multi-Tenancy

Tenant isolation must exist across:

- identity
- database
- Qdrant
- cache
- retrieval
- actions
- policy
- audit
- metrics

### Disaster Recovery

Recovery planning should include:

- PostgreSQL restore
- vector store recovery
- policy recovery
- configuration recovery
- deployment reconstruction
- RPO/RTO validation

### SRE

Operational maturity includes:

- SLIs
- SLOs
- error budgets
- alerts
- runbooks
- incident response
- postmortems

---

# Backend to Frontend Contract

The frontend should consume backend capabilities through HTTP APIs.

```text
Frontend                    Backend

Login              <---->   Authentication
Session            <---->   Current identity
Chat               <---->   RAG / Agent
Citations          <---->   Structured sources
Tool status        <---->   Agent/tool metadata
Approvals          <---->   Pending actions
Action timeline    <---->   Action state machine
Incident UI        <---->   Incident APIs
Job status         <---->   Worker/job state
Audit UI           <---->   Audit events
```

The frontend should not directly connect to infrastructure services.

---

# Branch Verification

Because merged feature branches may be deleted, use Git history in addition to branch listings.

### Remote branches

```bash
git fetch --all --prune
git branch -r
```

### Local and remote

```bash
git branch -a
```

### Full commit graph

```bash
git log --graph --decorate --oneline --all
```

### Merged remote branches

```bash
git branch -r --merged origin/main
```

### Exact refs

```bash
git for-each-ref --format='%(refname:short)' refs/heads/ refs/remotes/
```

---

# Engineering Summary

The project is not just a RAG application.

It combines:

```text
RAG
Agentic AI
MCP
Kubernetes
authorization
human approval
durable workers
PostgreSQL
OPA
observability
CI/CD
performance engineering
```

into one operationally controlled AI platform.

The key design choice throughout the system is that probabilistic AI behavior is surrounded by deterministic software controls for identity, authorization, state, execution, verification, and audit.

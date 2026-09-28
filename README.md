# AI IT Support Assistant

A production-oriented **GenAI and Agentic AI platform for IT support and infrastructure operations**.

The platform combines enterprise knowledge retrieval, live operational tooling, policy-based authorization, human approvals, durable execution, and observability in a single backend service.

It is designed to answer support questions from internal documentation, inspect live Kubernetes state, and safely coordinate protected operational actions without giving an LLM unrestricted access to infrastructure.

---

## Overview

Traditional IT support systems usually separate documentation search, operational dashboards, ticketing, and infrastructure tooling.

This project brings those workflows together behind one AI-assisted interface.

The assistant can:

- answer questions using internal documentation
- retrieve semantically relevant evidence from Qdrant
- generate grounded responses with source citations
- decide whether a request should use RAG or a live tool
- inspect Kubernetes resources through controlled read-only tools
- create and manage operational actions
- require approval before protected writes
- execute approved actions through durable workers
- verify the real outcome of infrastructure changes
- enforce authorization through a centralized policy layer
- expose controlled tools through MCP
- emit logs, metrics, traces, and audit records for production operations

---

## Architecture

```text
                         ┌────────────────────┐
                         │       Client       │
                         └─────────┬──────────┘
                                   │
                                   ▼
                         ┌────────────────────┐
                         │      FastAPI       │
                         │    API Gateway     │
                         └─────────┬──────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
                    ▼                             ▼
          ┌──────────────────┐          ┌──────────────────┐
          │ Authentication   │          │ Authorization    │
          │ Identity Context │          │ Policy Decision  │
          └────────┬─────────┘          └────────┬─────────┘
                   │                             │
                   └──────────────┬──────────────┘
                                  ▼
                        ┌────────────────────┐
                        │    Agent Router    │
                        └───────┬─────┬──────┘
                                │     │
                         ┌──────┘     └─────────┐
                         ▼                      ▼
               ┌──────────────────┐   ┌──────────────────┐
               │       RAG        │   │   Live Tools     │
               │                  │   │                  │
               │ Qdrant           │   │ Kubernetes       │
               │ Embeddings       │   │ Incident Actions │
               │ Ollama / LLM     │   │ MCP              │
               └────────┬─────────┘   └────────┬─────────┘
                        │                      │
                        └──────────┬───────────┘
                                   ▼
                         ┌────────────────────┐
                         │ Structured Result  │
                         │ Citations / Status │
                         └────────────────────┘
```

Protected write operations follow a separate execution path:

```text
Request
   │
   ▼
Authorization
   │
   ▼
Pending Action
   │
   ▼
Human Approval
   │
   ▼
Durable Worker
   │
   ▼
External System
   │
   ▼
Verification
   │
   ▼
Audit Trail
```

The LLM never acts as the final security boundary.

---

## Core Capabilities

### Retrieval-Augmented Generation

The RAG pipeline supports:

- document upload
- text extraction
- chunking with overlap
- source metadata
- embeddings
- Qdrant vector indexing
- semantic retrieval
- grounded generation
- structured LLM output
- source citations
- abstention behavior
- retrieval and answer evaluation

RAG flow:

```text
Document
   │
   ▼
Extraction
   │
   ▼
Chunking
   │
   ▼
Embeddings
   │
   ▼
Qdrant
   │
   ▼
Retrieval
   │
   ▼
Grounded LLM Response
```

---

### Agent Routing

The assistant does not assume every question should go through RAG.

Examples:

```text
"How do I reset the corporate VPN?"
            │
            ▼
           RAG
```

```text
"Is ai-support-api healthy right now?"
            │
            ▼
   Kubernetes Read Tool
```

The agent chooses the appropriate backend capability based on the request.

---

### Controlled Operational Actions

Protected actions are never executed directly from model output.

Example:

```text
User requests deployment restart
             │
             ▼
Agent proposes action
             │
             ▼
Authorization
             │
             ▼
Pending approval
             │
             ▼
Human approval
             │
             ▼
Worker executes
             │
             ▼
Rollout verification
             │
             ▼
Audit event
```

This architecture provides:

- explicit action states
- concurrency protection
- idempotency
- durable execution
- human approval
- post-action verification
- complete audit history

---

### Authorization and Policy

Authorization is centralized rather than scattered across individual endpoints.

Policy decisions are evaluated using:

```text
subject
resource
action
context
```

Example:

```text
subject  = user-123
resource = deployment/ai-support-api
action   = restart
context  = production
```

The platform supports an external Open Policy Agent policy decision point.

Protected operations are designed to fail closed when authorization cannot be evaluated safely.

---

### MCP Integration

Selected tools can be exposed through MCP while preserving the same backend controls.

MCP does not bypass:

- authentication
- authorization
- approval
- audit
- idempotency
- execution state
- verification

---

### Observability

The system is instrumented across:

- HTTP requests
- RAG operations
- agent routing
- tool calls
- policy decisions
- workers
- database access
- external actions

Observability includes:

- structured logging
- request correlation
- latency measurements
- Prometheus metrics
- OpenTelemetry traces
- operational audit events

---

## Technology Stack

### Application

- Python
- FastAPI
- Pydantic
- Pydantic Settings
- Uvicorn

### Data

- PostgreSQL
- SQLAlchemy
- Alembic
- Qdrant

### AI

- Ollama
- embeddings
- Vector RAG
- structured LLM outputs
- agent routing
- MCP

### Security

- application authentication
- resource-level authorization
- centralized policy decisions
- Open Policy Agent

### Infrastructure

- Docker
- Docker Compose
- Kubernetes
- Prometheus
- OpenTelemetry

### Engineering

- `uv`
- `pytest`
- Ruff
- GitHub Actions
- automated AI evaluation
- performance/load testing

---

## Repository Structure

```text
.
├── .github/
│   └── workflows/               # CI/CD workflows
│
├── data/
│   └── evaluation/              # Evaluation datasets
│
├── docs/                        # Architecture and operational documentation
│
├── k8s/                         # Kubernetes deployment resources
│
├── migrations/                  # Alembic database migrations
│
├── observability/               # Metrics and tracing configuration
│
├── opa/                         # OPA policies and bundles
│
├── performance/                 # Load and capacity tests
│
├── sample_files/                # Documents used for local testing
│
├── scripts/                     # Operational and utility scripts
│
├── src/
│   └── ai_it_support_assistant/
│       ├── api/                 # HTTP routes
│       ├── core/                # Configuration and shared application logic
│       ├── models/              # Data/domain models
│       ├── services/            # Business and AI services
│       └── main.py              # FastAPI application entrypoint
│
├── tests/                       # Unit, integration, security, and workflow tests
├── .env.example
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── uv.lock
```

> Exact internal package folders may evolve as the project grows.

---

## Data Model

The application persists operational state in PostgreSQL.

Current persisted domains include:

```text
users
resource_permissions
incidents
pending_actions
audit_events
```

Alembic is used for versioned schema changes.

---

## Local Development

### Prerequisites

Install:

- Python
- `uv`
- Docker
- Docker Compose
- Ollama

Optional local dependencies can be started through Docker Compose where configured.

---

### Clone

```bash
git clone https://github.com/siri-chandanak/ai-it-support-assistant.git
cd ai-it-support-assistant
```

---

### Install Dependencies

```bash
uv sync
```

---

### Configure Environment

```bash
cp .env.example .env
```

Update the values required for your local environment.

Do not commit:

- passwords
- API keys
- private keys
- access tokens
- production credentials

---

### Start Dependencies

```bash
docker compose up -d
```

---

### Start the API

```bash
uv run uvicorn ai_it_support_assistant.main:app --app-dir src --reload
```

---

### Run Tests

```bash
uv run pytest
```

---

### Run Linting

```bash
uv run ruff check .
```

---

## Development Workflow

Development follows a feature-branch model.

```text
main
 │
 └── feature/<capability>
          │
          ├── implementation
          ├── tests
          ├── local validation
          ├── GitHub Actions
          ├── pull request
          └── merge
```

Typical workflow:

```bash
git checkout main
git pull
git status

git checkout -b feature/example-capability

# implementation

uv run pytest
uv run ruff check .

git add .
git commit -m "Add example capability"
git push -u origin feature/example-capability
```

---

## Testing Strategy

The project treats AI quality and platform reliability as separate but related concerns.

Testing covers:

### Application Tests

- API behavior
- validation
- services
- database operations
- worker behavior

### RAG Tests

- retrieval relevance
- top-k behavior
- grounding
- citations
- abstention

### Security Tests

- unauthorized access
- document leakage
- permission enforcement
- cache isolation
- policy decisions

### Agent Tests

- routing
- tool selection
- read-only execution
- protected write behavior

### Operational Tests

- worker recovery
- idempotency
- rollout verification
- dependency failures
- concurrency
- end-to-end workflows

### Performance Tests

- throughput
- p50 / p95 / p99 latency
- Qdrant latency
- database pressure
- worker throughput
- cache effectiveness
- policy latency
- load saturation

---

## CI/CD

GitHub Actions is used to validate changes before merge.

Typical checks include:

```text
dependency installation
        ↓
linting
        ↓
tests
        ↓
AI evaluations
        ↓
security/policy checks
        ↓
build validation
```

Deployment-related workflows are kept separate from basic PR validation.

---

## Security Model

The backend is the security boundary.

A future frontend should communicate only with FastAPI.

It should not connect directly to:

```text
PostgreSQL
Qdrant
Kubernetes
Ollama
OPA
internal MCP servers
```

All sensitive operations must pass through:

```text
identity
authorization
validation
audit
```

---

## Production Engineering

The platform includes engineering work around:

- retries
- timeouts
- backoff
- cache behavior
- database connection pressure
- worker throughput
- policy availability
- Kubernetes readiness
- release verification
- performance baselines
- capacity limits

The goal is to derive operational settings from measurements rather than static guesses.

---

## Future Development

The architecture is designed to support additional capabilities including:

- asynchronous ingestion
- document lifecycle management
- hybrid search
- reranking
- query expansion
- Graph RAG
- service dependency graphs
- durable investigations
- human escalation
- Jira / ServiceNow integration
- feedback loops
- prompt and model versioning
- canary releases
- secret management
- workload identity
- red-team regression testing
- multi-tenancy
- backup and restore
- SRE operations

---

## Frontend

The planned frontend stack is:

- Next.js
- React
- TypeScript
- Tailwind CSS
- TanStack Query
- Zod
- React Hook Form
- Vitest
- React Testing Library
- Playwright

The UI will cover:

- login and session handling
- RAG chat
- citations
- live tool results
- action approvals
- incidents
- job status
- audit history
- document upload
- operational workflows

---

## Engineering Guide

For a detailed explanation of the project's feature branches, architecture evolution, implementation decisions, and capability ownership, see:

[`project_guide.md`](./project_guide.md)

---

## Project Status

Active development.

The backend contains the core architecture required for frontend development and continued platform expansion.

Production deployment should still be validated against the target environment's real identity provider, infrastructure, security requirements, traffic profile, operational controls, and recovery procedures.

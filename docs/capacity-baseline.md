# Capacity Baseline

## Purpose

This document records measured system capacity.

Values in this document must come from benchmark or staging
measurements rather than guesses.

---

## Environment

Environment:

Git SHA:

Image digest:

Test date:

API version:

Embedding model:

LLM model:

Qdrant collection:

RAG top_k:

RAG score threshold:

Cache enabled:

PDP mode:

---

## API

API replicas:

CPU request per replica:

CPU limit per replica:

Memory request per replica:

Memory limit per replica:

Sustained RAG concurrency:

Maximum tested concurrency:

RAG p50:

RAG p95:

RAG p99:

Maximum acceptable throughput:

HTTP error rate:

Observed saturation point:

---

## Embeddings

Model:

Device:

### Batch Size 1

Total duration:

Queries/sec:

Average ms/query:

### Batch Size 10

Total duration:

Queries/sec:

Average ms/query:

### Batch Size 100

Total duration:

Queries/sec:

Average ms/query:

---

## Qdrant

Collection:

Vector count:

Vector dimensions:

### top_k = 3

p50:

p95:

p99:

### top_k = 5

p50:

p95:

p99:

### top_k = 10

p50:

p95:

p99:

### top_k = 20

p50:

p95:

p99:

Authorization-filter impact:

Collection-size impact:

---

## PostgreSQL

Database connection limit:

API replicas:

API pool size:

API max overflow:

MCP replicas:

MCP pool size:

MCP max overflow:

Worker replicas:

Worker pool size:

Worker max overflow:

Reserved admin/migration connections:

Calculated maximum application connection pressure:

Peak observed connections:

Connection acquisition p95:

Pool timeouts:

Pool exhaustion observed:

---

## Worker

Worker replicas:

Incident actions completed:

Incident test duration:

Incident throughput:

Average incident duration:

Restart test count:

Average restart duration:

Maximum safe restart concurrency:

Peak queue depth:

Queue delay p50:

Queue delay p95:

Queue delay p99:

---

## Cache

Embedding cache hits:

Embedding cache misses:

Embedding cache hit ratio:

Retrieval cache hits:

Retrieval cache misses:

Retrieval cache hit ratio:

Warm RAG p95:

Cold RAG p95:

---

## MCP

Concurrent sessions:

Tool discovery p95:

Knowledge-search p95:

Service-status p95:

Kubernetes-read p95:

---

## OPA

PDP mode:

OPA concurrency tested:

OPA p50:

OPA p95:

OPA p99:

Failure behavior:

Unauthorized false allows:

---

## Practical Capacity

Measured saturation knee:

Recommended operating concurrency:

Recommended operating throughput:

Recommended headroom:

N-1 tested capacity:

Recommended API autoscaling signal:

Recommended worker autoscaling signal:

---

## Notes

Production operating capacity should remain below the measured
saturation knee.

Capacity must include headroom for:

- traffic bursts
- pod failures
- dependency degradation
- deployment rollouts
- node replacement
- retry overhead
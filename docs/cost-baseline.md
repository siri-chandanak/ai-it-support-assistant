# Cost Baseline

## Purpose

This document records the estimated cost of operating the AI IT
Support Assistant.

It separates variable request cost from fixed or semi-fixed
infrastructure cost.

---

## Environment

Environment:

Git SHA:

Date:

LLM provider:

LLM model:

Embedding provider:

Embedding model:

---

## LLM

Average input tokens:

Average output tokens:

Average total tokens:

Input cost per million tokens:

Output cost per million tokens:

Estimated direct LLM cost per RAG answer:

Estimated direct LLM cost per 1,000 RAG answers:

Estimated direct LLM cost per 10,000 RAG answers:

---

## RAG Configuration

Top-K:

Average retrieved chunks:

Average context tokens:

Average answer tokens:

RAG evaluation pass rate:

RAG p95 latency:

---

## Top-K Cost Comparison

| top_k | Avg Input Tokens | RAG p95 | Eval Pass Rate | Cost / Answer |
|---:|---:|---:|---:|---:|
| 3 | | | | |
| 5 | | | | |
| 10 | | | | |
| 20 | | | | |

---

## Infrastructure

### API

Replicas:

CPU:

Memory:

Estimated monthly cost:

### Workers

Replicas:

CPU:

Memory:

Estimated monthly cost:

### PostgreSQL

Configuration:

Estimated monthly cost:

### Qdrant

Configuration:

Estimated monthly cost:

### OPA

Configuration:

Estimated monthly cost:

### OpenTelemetry

Collector configuration:

Estimated monthly cost:

### Other

Network:

Storage:

Monitoring:

Estimated monthly cost:

---

## Fixed Monthly Infrastructure Estimate

Estimated fixed monthly infrastructure cost:

---

## Variable Request Cost

Estimated cost per RAG answer:

Estimated cost per 1,000 RAG answers:

Estimated cost per 10,000 RAG answers:

Estimated cost per 100,000 RAG answers:

---

## Quality-Adjusted Cost

RAG evaluation pass rate:

Estimated cost per successful grounded answer:

Formula:

cost per successful grounded answer =
average request cost / grounded-answer success rate

Example:

If:

average request cost = $0.002

and:

grounded-answer success rate = 0.90

then:

cost per successful grounded answer =
$0.002 / 0.90
= $0.00222

---

## Local Model Note

A local model such as Ollama may have zero per-token API billing.

That does not mean production inference is free.

Local inference still consumes resources such as:

- CPU
- GPU
- memory
- nodes
- electricity
- storage
- operational capacity

Those costs belong under infrastructure rather than provider
token pricing.

### RAG latency budget

Initial target:
- p95 < 3.0 seconds

Measured 30-request development baseline:
- p50: 3.66 seconds
- p95: 5.40 seconds
- p99: 7.05 seconds
- error rate: 0%

Supporting component measurements:
- Qdrant secured p95: ~145 ms
- retrieval p95: ~732 ms
- LLM short-context p95: ~2.45 s
- LLM production-context p95: ~3.75 s

The primary latency contributor is LLM generation with
production-sized retrieved context and provider latency variance.

For the Step 34 development readiness baseline, the RAG p95
budget is therefore set to 6.0 seconds.

The 3.0-second value remains the optimization target and is not
being claimed as currently achieved.

A 25% regression guard is retained against the measured baseline.
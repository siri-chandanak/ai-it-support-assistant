from prometheus_client import Counter, Gauge, Histogram

# ============================================================
# HTTP METRICS
# ============================================================

HTTP_REQUESTS = Counter(
    "ai_support_http_requests_total",
    "Total number of HTTP requests processed",
    [
        "method",
        "route",
        "status_class",
    ],
)

HTTP_REQUEST_DURATION = Histogram(
    "ai_support_http_request_duration_seconds",
    "HTTP request duration in seconds",
    [
        "method",
        "route",
    ],
)


# ============================================================
# RAG METRICS
# ============================================================

RAG_RETRIEVAL_REQUESTS = Counter(
    "ai_support_rag_retrieval_requests_total",
    "Total number of RAG retrieval requests",
)

RAG_RETRIEVAL_FAILURES = Counter(
    "ai_support_rag_retrieval_failures_total",
    "Total number of RAG retrieval failures",
)

RAG_RETRIEVED_CHUNKS = Histogram(
    "ai_support_rag_retrieved_chunks",
    "Number of chunks returned by retrieval",
)

RAG_RETRIEVAL_DURATION = Histogram(
    "ai_support_rag_retrieval_duration_seconds",
    "RAG retrieval duration in seconds",
)

RAG_ABSTENTIONS = Counter(
    "ai_support_rag_abstentions_total",
    "Total number of RAG abstentions",
    ["reason"],
)

RAG_DURATION = Histogram(
    "ai_support_rag_duration_seconds",
    "Total RAG pipeline duration in seconds",
    ["outcome"],
)


# ============================================================
# LLM METRICS
# ============================================================

LLM_REQUESTS = Counter(
    "ai_support_llm_requests_total",
    "Total number of LLM requests",
    ["model"],
)

LLM_FAILURES = Counter(
    "ai_support_llm_failures_total",
    "Total number of LLM request failures",
    ["model"],
)

LLM_DURATION = Histogram(
    "ai_support_llm_duration_seconds",
    "LLM request duration in seconds",
    ["model"],
)


# ============================================================
# AGENT ROUTING METRICS
# ============================================================

AGENT_REQUESTS = Counter(
    "ai_support_agent_requests_total",
    "Total number of agent requests",
)

AGENT_ROUTE = Counter(
    "ai_support_agent_route_total",
    "Total number of agent routing decisions",
    ["action"],
)

AGENT_ROUTING_FAILURES = Counter(
    "ai_support_agent_routing_failures_total",
    "Total number of agent routing failures",
)

AGENT_DURATION = Histogram(
    "ai_support_agent_duration_seconds",
    "Agent request duration in seconds",
)


# ============================================================
# POLICY / PDP METRICS
# ============================================================

POLICY_DECISIONS = Counter(
    "ai_support_policy_decisions_total",
    "Total number of policy decisions",
    [
        "action",
        "result",
        "reason_code",
        "pdp_mode",
    ],
)

POLICY_DENIALS = Counter(
    "ai_support_policy_denials_total",
    "Total number of policy denials",
    [
        "action",
        "reason_code",
        "pdp_mode",
    ],
)

POLICY_ERRORS = Counter(
    "ai_support_policy_errors_total",
    "Total number of policy evaluation errors",
    [
        "action",
        "pdp_mode",
    ],
)

POLICY_DURATION = Histogram(
    "ai_support_policy_duration_seconds",
    "Policy evaluation duration in seconds",
    [
        "action",
        "pdp_mode",
    ],
)


# ============================================================
# OPA METRICS
# ============================================================

OPA_REQUESTS = Counter(
    "ai_support_opa_requests_total",
    "Total number of requests sent to OPA",
)

OPA_FAILURES = Counter(
    "ai_support_opa_failures_total",
    "Total number of OPA request failures",
)

OPA_TIMEOUTS = Counter(
    "ai_support_opa_timeouts_total",
    "Total number of OPA request timeouts",
)

OPA_DURATION = Histogram(
    "ai_support_opa_duration_seconds",
    "OPA request duration in seconds",
)

OPA_SHADOW_MISMATCHES = Counter(
    "ai_support_opa_shadow_mismatch_total",
    "Number of mismatches between primary and shadow policy decisions",
)


# ============================================================
# APPROVAL METRICS
# ============================================================

ACTION_PROPOSALS = Counter(
    "ai_support_action_proposals_total",
    "Total number of action proposals",
    ["action_type"],
)

ACTION_APPROVALS = Counter(
    "ai_support_action_approvals_total",
    "Total number of approved actions",
    ["action_type"],
)

ACTION_REJECTIONS = Counter(
    "ai_support_action_rejections_total",
    "Total number of rejected actions",
    ["action_type"],
)

# ---------------------------------------------------------
# Action state machine
# ---------------------------------------------------------

ACTION_STATE_TRANSITIONS = Counter(
    "ai_support_action_state_transitions_total",
    "Total durable action state transitions",
    [
        "action_type",
        "from_state",
        "to_state",
    ],
)


# ============================================================
# WORKER METRICS
# ============================================================

WORKER_ACTIONS_CLAIMED = Counter(
    "ai_support_worker_actions_claimed_total",
    "Total number of actions claimed by workers",
    ["action_type"],
)

WORKER_ACTIONS_SUCCEEDED = Counter(
    "ai_support_worker_actions_succeeded_total",
    "Total number of successfully completed actions",
    ["action_type"],
)

WORKER_ACTIONS_FAILED = Counter(
    "ai_support_worker_actions_failed_total",
    "Total number of failed worker actions",
    [
        "action_type",
        "failure_reason",
    ],
)

WORKER_STALE_ACTIONS_RECOVERED = Counter(
    "ai_support_worker_stale_actions_recovered_total",
    "Total number of stale actions recovered",
    ["action_type"],
)

WORKER_CLAIM_CONFLICTS = Counter(
    "ai_support_worker_claim_conflicts_total",
    "Total number of worker claim conflicts",
    ["action_type"],
)

ACTION_QUEUE_DEPTH = Gauge(
    "ai_support_action_queue_depth",
    "Number of approved actions waiting for worker execution",
)

ACTION_EXECUTING = Gauge(
    "ai_support_action_executing",
    "Number of actions currently executing",
    ["action_type"],
)

ACTION_QUEUE_DELAY = Histogram(
    "ai_support_action_queue_delay_seconds",
    "Delay between action approval and worker execution start",
    ["action_type"],
)

ACTION_EXECUTION_DURATION = Histogram(
    "ai_support_action_execution_duration_seconds",
    "Worker action execution duration in seconds",
    [
        "action_type",
        "outcome",
    ],
)


# ============================================================
# KUBERNETES METRICS
# ============================================================

KUBERNETES_READS = Counter(
    "ai_support_kubernetes_reads_total",
    "Total number of Kubernetes read operations",
    ["operation"],
)

KUBERNETES_WRITE_ATTEMPTS = Counter(
    "ai_support_kubernetes_write_attempts_total",
    "Total number of Kubernetes write attempts",
    ["operation"],
)

KUBERNETES_WRITE_FAILURES = Counter(
    "ai_support_kubernetes_write_failures_total",
    "Total number of Kubernetes write failures",
    [
        "operation",
        "reason",
    ],
)

DEPLOYMENT_RESTART_DURATION = Histogram(
    "ai_support_deployment_restart_duration_seconds",
    "Deployment restart duration in seconds",
)

DEPLOYMENT_ROLLOUT_TIMEOUTS = Counter(
    "ai_support_deployment_rollout_timeouts_total",
    "Total number of deployment rollout timeouts",
)

DEPLOYMENT_ROLLOUT_FAILURES = Counter(
    "ai_support_deployment_rollout_failures_total",
    "Total number of deployment rollout failures",
    ["reason"],
)

# ---------------------------------------------------------
# MCP
# ---------------------------------------------------------

MCP_TOOL_CALLS = Counter(
    "ai_support_mcp_tool_calls_total",
    "Total MCP tool calls",
    ["tool", "outcome"],
)

MCP_TOOL_DENIALS = Counter(
    "ai_support_mcp_tool_denials_total",
    "Total MCP tool calls denied by authorization",
    ["tool"],
)

MCP_TOOL_DURATION = Histogram(
    "ai_support_mcp_tool_duration_seconds",
    "MCP tool execution duration",
    ["tool"],
)

MCP_RESOURCE_READS = Counter(
    "ai_support_mcp_resource_reads_total",
    "Total MCP resource reads",
    ["resource_type", "outcome"],
)


LLM_INPUT_TOKENS = Counter(
    "ai_support_llm_input_tokens_total",
    "Total LLM input tokens.",
    ["model", "operation"],
)

LLM_OUTPUT_TOKENS = Counter(
    "ai_support_llm_output_tokens_total",
    "Total LLM output tokens.",
    ["model", "operation"],
)

LLM_ESTIMATED_COST_TOTAL = Counter(
    "ai_support_llm_estimated_cost",
    "Estimated direct LLM cost.",
    ["model", "operation"],
)

EMBEDDING_CACHE_HITS = Counter(
    "ai_support_embedding_cache_hits",
    "Embedding cache hits",
)


EMBEDDING_CACHE_MISSES = Counter(
    "ai_support_embedding_cache_misses",
    "Embedding cache misses",
)


RETRIEVAL_CACHE_HITS = Counter(
    "ai_support_retrieval_cache_hits",
    "Retrieval cache hits",
)


RETRIEVAL_CACHE_MISSES = Counter(
    "ai_support_retrieval_cache_misses",
    "Retrieval cache misses",
)

embedding_cache_hits_total = Counter(
    "embedding_cache_hits_total",
    "Total embedding cache hits.",
)


embedding_cache_misses_total = Counter(
    "embedding_cache_misses_total",
    "Total embedding cache misses.",
)


retrieval_cache_hits_total = Counter(
    "retrieval_cache_hits_total",
    "Total retrieval cache hits.",
)


retrieval_cache_misses_total = Counter(
    "retrieval_cache_misses_total",
    "Total retrieval cache misses.",
)

# ---------------------------------------------------------
# Helper functions
# ---------------------------------------------------------


def record_worker_failure(
    *,
    action_type: str,
    failure_reason: str,
) -> None:
    """
    Record one worker action failure.

    failure_reason must be a bounded, controlled value.

    Good:
        rollout_timeout
        authorization_denied
        kubernetes_unavailable
        incident_creation_failed
        unknown_internal_error

    Never pass:
        str(exception)
        approval_id
        username
        request_id
        trace_id
    """

    WORKER_ACTIONS_FAILED.labels(
        action_type=action_type,
        failure_reason=failure_reason,
    ).inc()


def record_worker_success(
    *,
    action_type: str,
) -> None:
    """
    Record successful completion of one worker action.
    """

    WORKER_ACTIONS_SUCCEEDED.labels(
        action_type=action_type,
    ).inc()

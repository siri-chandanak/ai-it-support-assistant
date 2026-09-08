import logging

from ai_it_support_assistant.core.request_context import (
    get_request_id,
)
from ai_it_support_assistant.schemas.agent import (
    AgentResponse,
)
from ai_it_support_assistant.schemas.auth import User
from ai_it_support_assistant.services.agent_router_service import (
    AgentRoutingError,
    route_agent_request,
)
from ai_it_support_assistant.services.live_status_service import (
    get_live_service_status,
)
from ai_it_support_assistant.services.rag_service import (
    answer_question,
)
from ai_it_support_assistant.services.tool_authorization_service import (
    authorize_tool,
)

logger = logging.getLogger(__name__)


def handle_agent_request(
    *,
    question: str,
    current_user: User,
    embedding_model_name: str,
    qdrant_url: str,
    collection_name: str,
    qdrant_timeout_seconds: float,
    qdrant_max_attempts: int,
    rag_top_k: int,
    rag_score_threshold: float,
    openai_api_key: str,
    llm_model: str,
    openai_timeout_seconds: float,
    openai_max_retries: int,
    embedding_cache_enabled: bool,
    retrieval_cache_enabled: bool,
) -> AgentResponse:
    decision = route_agent_request(
        question=question,
        api_key=openai_api_key,
        model_name=llm_model,
        timeout_seconds=openai_timeout_seconds,
        max_retries=openai_max_retries,
    )
    logger.info(
        ("agent_decision request_id=%s action=%s"),
        get_request_id(),
        decision.action,
    )
    if decision.action == "rag":
        rag_response = answer_question(
            question=question,
            top_k=rag_top_k,
            score_threshold=rag_score_threshold,
            embedding_model_name=embedding_model_name,
            qdrant_url=qdrant_url,
            collection_name=collection_name,
            qdrant_timeout_seconds=qdrant_timeout_seconds,
            qdrant_max_attempts=qdrant_max_attempts,
            openai_api_key=openai_api_key,
            llm_model=llm_model,
            openai_timeout_seconds=openai_timeout_seconds,
            openai_max_retries=openai_max_retries,
            embedding_cache_enabled=embedding_cache_enabled,
            retrieval_cache_enabled=retrieval_cache_enabled,
            user_roles=current_user.roles,
        )

        return AgentResponse(
            question=question,
            action="rag",
            answer=rag_response.answer,
        )

    if decision.action == "live_status":
        authorize_tool(
            tool_name="live_status",
            user=current_user,
        )

        if decision.service_name is None:
            raise AgentRoutingError("Missing service name.")
        logger.info(
            ("tool_execution_started request_id=%s tool=live_status"),
            get_request_id(),
        )
        service_status = get_live_service_status(
            service_name=decision.service_name,
        )

        logger.info(
            ("tool_execution_completed request_id=%s tool=live_status status=%s"),
            get_request_id(),
            service_status.status,
        )

        answer = (
            f"{service_status.service_name} is {service_status.status}. {service_status.message}"
        )

        return AgentResponse(
            question=question,
            action="live_status",
            answer=answer,
        )

    raise AgentRoutingError("Unsupported agent action.")

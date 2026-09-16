from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ai_it_support_assistant.api.dependencies.auth import (
    get_current_user,
)
from ai_it_support_assistant.core.config import get_settings
from ai_it_support_assistant.db.session import (
    get_db,
)
from ai_it_support_assistant.schemas.agent import (
    AgentRequest,
    AgentResponse,
)
from ai_it_support_assistant.schemas.auth import User
from ai_it_support_assistant.services.agent_router_service import (
    AgentRoutingError,
)
from ai_it_support_assistant.services.agent_service import (
    handle_agent_request,
)
from ai_it_support_assistant.services.kubernetes_state_service import (
    KubernetesAccessError,
    KubernetesResourceNotFoundError,
    KubernetesStateError,
)
from ai_it_support_assistant.services.live_status_service import (
    ServiceNotFoundError,
)
from ai_it_support_assistant.services.policy_enforcement_service import (
    AuthorizationDeniedError,
)
from ai_it_support_assistant.services.policy_service import (
    PolicyEvaluationError,
)

router = APIRouter()


@router.post(
    "/agent/ask",
    response_model=AgentResponse,
)
def ask_agent(
    request: AgentRequest,
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
    session: Annotated[
        Session,
        Depends(get_db),
    ],
) -> AgentResponse:
    settings = get_settings()

    try:
        return handle_agent_request(
            question=request.question,
            current_user=current_user,
            session=session,
            embedding_model_name=settings.embedding_model_name,
            qdrant_url=settings.qdrant_url,
            collection_name=settings.qdrant_collection_name,
            qdrant_timeout_seconds=(settings.qdrant_timeout_seconds),
            qdrant_max_attempts=(settings.qdrant_max_attempts),
            rag_top_k=settings.rag_top_k,
            rag_score_threshold=(settings.rag_score_threshold),
            openai_api_key=settings.openai_api_key,
            llm_model=settings.llm_model,
            openai_timeout_seconds=(settings.openai_timeout_seconds),
            openai_max_retries=(settings.openai_max_retries),
            kubernetes_config_mode=(settings.kubernetes_config_mode),
            kubernetes_context=(settings.kubernetes_context),
            kubernetes_default_namespace=(settings.kubernetes_default_namespace),
            kubernetes_write_enabled=settings.kubernetes_write_enabled,
            kubernetes_restart_allowed_namespaces=(settings.kubernetes_restart_allowed_namespaces),
            kubernetes_restart_allowed_deployments=(
                settings.kubernetes_restart_allowed_deployments
            ),
            embedding_cache_enabled=(settings.embedding_cache_enabled),
            retrieval_cache_enabled=(settings.retrieval_cache_enabled),
        )

    except AuthorizationDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to access the requested resource.",
        ) from exc

    except ServiceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service was not found.",
        ) from exc

    except PolicyEvaluationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authorization service is unavailable.",
        ) from exc

    except AgentRoutingError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to route request.",
        ) from exc

    except KubernetesResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kubernetes resource was not found.",
        ) from exc

    except KubernetesAccessError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Kubernetes state is unavailable.",
        ) from exc

    except KubernetesStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Kubernetes state is unavailable.",
        ) from exc

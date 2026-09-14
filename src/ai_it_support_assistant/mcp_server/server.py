import json
from collections.abc import Callable
from typing import Literal

from mcp.server import MCPServer
from mcp.server.auth.settings import AuthSettings
from pydantic import AnyHttpUrl

from ai_it_support_assistant.core.config import get_settings
from ai_it_support_assistant.db.session import SessionLocal
from ai_it_support_assistant.mcp_server.auth import (
    ApplicationTokenVerifier,
)
from ai_it_support_assistant.mcp_server.identity import (
    get_mcp_current_user,
)
from ai_it_support_assistant.schemas.auth import User
from ai_it_support_assistant.schemas.incident import (
    IncidentCreateRequest,
)
from ai_it_support_assistant.services.action_proposal_service import (
    prepare_incident_action,
    prepare_restart_action,
)
from ai_it_support_assistant.services.approval_service import (
    get_pending_action_for_user,
)
from ai_it_support_assistant.services.kubernetes_state_service import (
    get_kubernetes_resource_state,
)
from ai_it_support_assistant.services.live_status_service import (
    get_live_service_status,
)
from ai_it_support_assistant.services.resource_authorization_service import (
    require_namespace_permission,
)
from ai_it_support_assistant.services.retrieval_service import (
    retrieve_chunks,
)
from ai_it_support_assistant.services.tool_authorization_service import (
    authorize_tool,
)


def register_mcp_capabilities(
    *,
    server: MCPServer,
    current_user_provider: Callable[[], User],
) -> None:
    @server.tool()
    def get_service_status(
        service_name: str,
    ) -> dict[str, object]:
        """Read the current health of a known service."""
        current_user = current_user_provider()

        authorize_tool(
            tool_name="live_status",
            user=current_user,
        )

        result = get_live_service_status(
            service_name=service_name,
        )

        return result.model_dump()

    @server.tool()
    def get_kubernetes_state(
        resource_type: Literal["deployment", "pod"],
        resource_name: str,
        namespace: str,
    ) -> dict[str, object]:
        current_user = current_user_provider()

        authorize_tool(
            tool_name="kubernetes_state",
            user=current_user,
        )

        with SessionLocal() as session:
            require_namespace_permission(
                user=current_user,
                permission="kubernetes:read",
                namespace=namespace,
                session=session,
            )

        settings = get_settings()

        result = get_kubernetes_resource_state(
            resource_type=resource_type,
            name=resource_name,
            namespace=namespace,
            config_mode=settings.kubernetes_config_mode,
            context=settings.kubernetes_context,
        )

        return result.model_dump()

    @server.tool()
    def search_knowledge(
        query: str,
        top_k: int = 3,
    ) -> list[dict[str, object]]:
        """Search authorized internal knowledge and return relevant evidence."""
        current_user = current_user_provider()
        settings = get_settings()

        chunks = retrieve_chunks(
            query=query,
            top_k=top_k,
            embedding_model_name=settings.embedding_model_name,
            embedding_cache_enabled=settings.embedding_cache_enabled,
            retrieval_cache_enabled=settings.retrieval_cache_enabled,
            qdrant_url=settings.qdrant_url,
            collection_name=settings.qdrant_collection_name,
            qdrant_timeout_seconds=settings.qdrant_timeout_seconds,
            qdrant_max_retries=settings.qdrant_max_attempts,
            user_roles=current_user.roles,
        )

        return [chunk.model_dump() for chunk in chunks]

    @server.tool()
    def propose_incident(
        title: str,
        description: str,
        severity: str,
        service_name: str | None = None,
    ) -> dict[str, object]:
        """Propose an incident for approval without executing creation."""
        current_user = current_user_provider()

        incident_request = IncidentCreateRequest(
            title=title,
            description=description,
            severity=severity,
            service_name=service_name,
        )

        with SessionLocal() as session:
            pending = prepare_incident_action(
                session=session,
                current_user=current_user,
                request=incident_request,
            )

            session.commit()

        return {
            "approval_required": True,
            "approval_id": pending.approval_id,
            "state": pending.state,
            "action": pending.action,
            "proposed_incident": incident_request.model_dump(),
        }

    @server.tool()
    def propose_restart_deployment(
        deployment_name: str,
        namespace: str,
    ) -> dict[str, object]:
        """Propose a Kubernetes Deployment restart for approval.

        This tool does not perform the restart.
        """
        current_user = current_user_provider()
        settings = get_settings()

        with SessionLocal() as session:
            pending, restart_payload = prepare_restart_action(
                session=session,
                current_user=current_user,
                deployment_name=deployment_name,
                namespace=namespace,
                kubernetes_write_enabled=(settings.kubernetes_write_enabled),
                kubernetes_restart_allowed_namespaces=(
                    settings.kubernetes_restart_allowed_namespaces
                ),
                kubernetes_restart_allowed_deployments=(
                    settings.kubernetes_restart_allowed_deployments
                ),
                kubernetes_config_mode=(settings.kubernetes_config_mode),
                kubernetes_context=(settings.kubernetes_context),
            )
            session.commit()

        return {
            "approval_required": True,
            "approval_id": pending.approval_id,
            "state": pending.state,
            "action": pending.action,
            "proposed_restart": restart_payload.model_dump(),
        }

    @server.resource(
        "action://{approval_id}",
        name="action_status",
        description=("Read the current status of an authorized pending action."),
    )
    def get_action_status(
        approval_id: str,
    ) -> dict[str, object]:
        current_user = current_user_provider()

        with SessionLocal() as session:
            action = get_pending_action_for_user(
                session=session,
                approval_id=approval_id,
                username=current_user.username,
                roles=current_user.roles,
            )

            payload = json.loads(
                action.payload_json,
            )

            result = json.loads(action.result_json) if action.result_json else None

            return {
                "approval_id": action.approval_id,
                "action": action.action,
                "requested_by": action.requested_by,
                "state": action.state,
                "payload": payload,
                "resource_id": action.resource_id,
                "failure_reason": action.failure_reason,
                "result": result,
                "version": action.version,
            }


def create_mcp_server(
    *,
    current_user_provider: Callable[[], User] = get_mcp_current_user,
) -> MCPServer:
    settings = get_settings()

    server = MCPServer(
        "AI IT Support Assistant",
        token_verifier=ApplicationTokenVerifier(),
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(
                settings.mcp_issuer_url,
            ),
            resource_server_url=AnyHttpUrl(
                settings.mcp_resource_server_url,
            ),
            required_scopes=[],
            validate_token_resource=False,
        ),
    )

    register_mcp_capabilities(
        server=server,
        current_user_provider=current_user_provider,
    )

    return server


mcp = create_mcp_server()

import asyncio
from uuid import uuid4

import pytest
from mcp import Client, MCPError

from ai_it_support_assistant.mcp_server.server import (
    create_mcp_server,
)
from ai_it_support_assistant.schemas.auth import User
from ai_it_support_assistant.schemas.policy import PolicyDecision


def make_user(
    *,
    username: str = "it-support",
    roles: list[str] | None = None,
) -> User:
    return User(
        user_id=uuid4(),
        username=username,
        roles=roles or ["it_support"],
        disabled=False,
    )


def tool_names(server) -> set[str]:
    return {tool.name for tool in server._tool_manager.list_tools()}


def test_mcp_server_registers_expected_tools():
    user = make_user()

    server = create_mcp_server(
        current_user_provider=lambda: user,
    )

    assert tool_names(server) == {
        "get_service_status",
        "get_kubernetes_state",
        "search_knowledge",
        "propose_incident",
        "propose_restart_deployment",
    }


def test_mcp_server_does_not_expose_dangerous_tools():
    user = make_user(
        username="admin",
        roles=["admin"],
    )

    server = create_mcp_server(
        current_user_provider=lambda: user,
    )

    forbidden_tools = {
        "approve_action",
        "reject_action",
        "execute_action",
        "execute_incident",
        "restart_deployment_now",
        "kubectl",
        "shell",
    }

    assert tool_names(server).isdisjoint(
        forbidden_tools,
    )


@pytest.mark.asyncio
async def test_reader_cannot_use_live_status():
    user = make_user(
        username="reader",
        roles=["reader"],
    )

    server = create_mcp_server(
        current_user_provider=lambda: user,
    )

    async with Client(server) as client:
        result = await client.call_tool(
            "get_service_status",
            {
                "service_name": "vpn-gateway",
            },
        )

    assert result.is_error is True


@pytest.mark.asyncio
async def test_it_support_can_use_live_status():
    user = make_user(
        username="it-support",
        roles=["it_support"],
    )

    server = create_mcp_server(
        current_user_provider=lambda: user,
    )

    async with Client(server) as client:
        result = await client.call_tool(
            "get_service_status",
            {
                "service_name": "vpn-gateway",
            },
        )

    assert result.is_error is False
    assert result.structured_content is not None
    assert result.structured_content["service_name"] == "vpn-gateway"


@pytest.mark.asyncio
async def test_reader_cannot_use_kubernetes_state():
    user = make_user(
        username="reader",
        roles=["reader"],
    )

    server = create_mcp_server(
        current_user_provider=lambda: user,
    )

    async with Client(server) as client:
        result = await client.call_tool(
            "get_kubernetes_state",
            {
                "resource_type": "deployment",
                "resource_name": "demo-api",
                "namespace": "ai-it-support-test",
            },
        )

    assert result.is_error is True


@pytest.mark.asyncio
async def test_reader_cannot_propose_incident():
    user = make_user(
        username="reader",
        roles=["reader"],
    )

    server = create_mcp_server(
        current_user_provider=lambda: user,
    )

    async with Client(server) as client:
        result = await client.call_tool(
            "propose_incident",
            {
                "title": "VPN authentication degradation",
                "description": ("Multiple users are reporting elevated authentication latency."),
                "severity": "medium",
                "service_name": "vpn-gateway",
            },
        )

    assert result.is_error is True


@pytest.mark.asyncio
async def test_it_support_cannot_propose_restart():
    user = make_user(
        username="it-support",
        roles=["it_support"],
    )

    server = create_mcp_server(
        current_user_provider=lambda: user,
    )

    async with Client(server) as client:
        result = await client.call_tool(
            "propose_restart_deployment",
            {
                "deployment_name": "demo-api",
                "namespace": "ai-it-support-test",
            },
        )

    assert result.is_error is True


@pytest.mark.asyncio
async def test_search_knowledge_uses_current_user_roles(
    monkeypatch,
):
    user = make_user(
        username="reader",
        roles=["reader"],
    )

    captured_roles: list[str] | None = None

    def fake_retrieve_chunks(
        *,
        query,
        top_k,
        embedding_model_name,
        embedding_cache_enabled,
        retrieval_cache_enabled,
        qdrant_url,
        collection_name,
        qdrant_timeout_seconds,
        qdrant_max_retries,
        user_roles,
    ):
        nonlocal captured_roles

        captured_roles = user_roles

        return []

    monkeypatch.setattr(
        ("ai_it_support_assistant.mcp_server.server.retrieve_chunks"),
        fake_retrieve_chunks,
    )

    server = create_mcp_server(
        current_user_provider=lambda: user,
    )

    async with Client(server) as client:
        result = await client.call_tool(
            "search_knowledge",
            {
                "query": "VPN troubleshooting",
                "top_k": 3,
            },
        )

    assert result.is_error is False
    assert captured_roles == ["reader"]


@pytest.mark.asyncio
async def test_propose_incident_creates_pending_action_only(
    monkeypatch,
):
    user = make_user(
        username="it-support",
        roles=["it_support"],
    )

    created: dict[str, object] = {}

    class FakePendingAction:
        approval_id = "APR-TEST1234"
        state = "pending"
        action = "create_incident"

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(
            self,
            exc_type,
            exc_value,
            traceback,
        ):
            return False

        def commit(self):
            created["committed"] = True

    def fake_session_local():
        return FakeSession()

    def fake_prepare_incident_action(
        *,
        session,
        current_user,
        request,
    ):
        created["username"] = current_user.username
        created["request"] = request

        return FakePendingAction()

    def fail_if_incident_executes(*args, **kwargs):
        raise AssertionError("Incident execution must not occur during MCP proposal creation.")

    monkeypatch.setattr(
        ("ai_it_support_assistant.mcp_server.server.SessionLocal"),
        fake_session_local,
    )

    monkeypatch.setattr(
        ("ai_it_support_assistant.mcp_server.server.prepare_incident_action"),
        fake_prepare_incident_action,
    )

    monkeypatch.setattr(
        ("ai_it_support_assistant.services.incident_service.create_incident"),
        fail_if_incident_executes,
    )

    server = create_mcp_server(
        current_user_provider=lambda: user,
    )

    async with Client(server) as client:
        result = await client.call_tool(
            "propose_incident",
            {
                "title": "VPN authentication degradation",
                "description": ("Multiple users are reporting elevated authentication latency."),
                "severity": "medium",
                "service_name": "vpn-gateway",
            },
        )

    assert result.is_error is False
    assert result.structured_content is not None

    assert result.structured_content["approval_required"] is True

    assert result.structured_content["approval_id"] == "APR-TEST1234"

    assert result.structured_content["state"] == "pending"

    assert result.structured_content["action"] == "create_incident"

    assert created["username"] == "it-support"
    assert created["committed"] is True

    request = created["request"]

    assert request.title == "VPN authentication degradation"
    assert request.severity == "medium"
    assert request.service_name == "vpn-gateway"


@pytest.mark.asyncio
async def test_propose_restart_creates_pending_action_only(
    monkeypatch,
):
    user = make_user(
        username="admin",
        roles=["admin"],
    )

    created: dict[str, object] = {}

    class FakePendingAction:
        approval_id = "APR-RESTART1"
        state = "pending"
        action = "restart_deployment"

    class FakeRestartPayload:
        def model_dump(self):
            return {
                "name": "demo-api",
                "namespace": "ai-it-support-test",
                "evidence_desired_replicas": 2,
                "evidence_ready_replicas": 2,
                "evidence_available_replicas": 2,
                "warnings": [],
            }

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(
            self,
            exc_type,
            exc_value,
            traceback,
        ):
            return False

        def commit(self):
            created["committed"] = True

    class FakeSettings:
        mcp_issuer_url = "http://127.0.0.1:8000"
        mcp_resource_server_url = "http://127.0.0.1:8001/mcp"

        kubernetes_write_enabled = True
        kubernetes_restart_allowed_namespaces = "ai-it-support-test"
        kubernetes_restart_allowed_deployments = "demo-api"
        kubernetes_config_mode = "local"
        kubernetes_context = "kind-kin"

    def fake_get_settings():
        return FakeSettings()

    def fake_session_local():
        return FakeSession()

    def fake_prepare_restart_action(
        *,
        session,
        current_user,
        deployment_name,
        namespace,
        kubernetes_write_enabled,
        kubernetes_restart_allowed_namespaces,
        kubernetes_restart_allowed_deployments,
        kubernetes_config_mode,
        kubernetes_context,
    ):
        created["username"] = current_user.username
        created["deployment_name"] = deployment_name
        created["namespace"] = namespace

        created["kubernetes_write_enabled"] = kubernetes_write_enabled
        created["allowed_namespaces"] = kubernetes_restart_allowed_namespaces
        created["allowed_deployments"] = kubernetes_restart_allowed_deployments
        created["config_mode"] = kubernetes_config_mode
        created["context"] = kubernetes_context

        return (
            FakePendingAction(),
            FakeRestartPayload(),
        )

    def fail_if_restart_executes(*args, **kwargs):
        raise AssertionError("Kubernetes restart must not execute during MCP proposal creation.")

    monkeypatch.setattr(
        ("ai_it_support_assistant.mcp_server.server.get_settings"),
        fake_get_settings,
    )

    monkeypatch.setattr(
        ("ai_it_support_assistant.mcp_server.server.SessionLocal"),
        fake_session_local,
    )

    monkeypatch.setattr(
        ("ai_it_support_assistant.mcp_server.server.prepare_restart_action"),
        fake_prepare_restart_action,
    )

    monkeypatch.setattr(
        ("ai_it_support_assistant.services.kubernetes_write_service.restart_deployment"),
        fail_if_restart_executes,
    )

    server = create_mcp_server(
        current_user_provider=lambda: user,
    )

    async with Client(server) as client:
        result = await client.call_tool(
            "propose_restart_deployment",
            {
                "deployment_name": "demo-api",
                "namespace": "ai-it-support-test",
            },
        )

    assert result.is_error is False
    assert result.structured_content is not None

    assert result.structured_content["approval_required"] is True

    assert result.structured_content["approval_id"] == "APR-RESTART1"

    assert result.structured_content["state"] == "pending"

    assert result.structured_content["action"] == "restart_deployment"

    assert created["username"] == "admin"
    assert created["deployment_name"] == "demo-api"
    assert created["namespace"] == "ai-it-support-test"
    assert created["committed"] is True

    assert created["kubernetes_write_enabled"] is True
    assert created["allowed_namespaces"] == "ai-it-support-test"
    assert created["allowed_deployments"] == "demo-api"
    assert created["config_mode"] == "local"
    assert created["context"] == "kind-kin"


@pytest.mark.asyncio
async def test_action_resource_owner_can_read(
    monkeypatch,
):
    user = make_user(
        username="it-support",
        roles=["it_support"],
    )

    class FakeAction:
        approval_id = "APR-OWNER1"
        action = "create_incident"
        requested_by = "it-support"
        state = "pending"
        payload_json = '{"title":"VPN issue"}'
        resource_id = None
        failure_reason = None
        result_json = None
        version = 1

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(
            self,
            exc_type,
            exc_value,
            traceback,
        ):
            return False

    def fake_session_local():
        return FakeSession()

    def fake_get_pending_action_for_user(
        *,
        session,
        approval_id,
        username,
        roles,
    ):
        assert approval_id == "APR-OWNER1"
        assert username == "it-support"
        assert roles == ["it_support"]

        return FakeAction()

    monkeypatch.setattr(
        ("ai_it_support_assistant.mcp_server.server.SessionLocal"),
        fake_session_local,
    )

    monkeypatch.setattr(
        ("ai_it_support_assistant.mcp_server.server.get_pending_action_for_user"),
        fake_get_pending_action_for_user,
    )

    server = create_mcp_server(
        current_user_provider=lambda: user,
    )

    async with Client(server) as client:
        resource = await client.read_resource("action://APR-OWNER1")

    assert resource is not None


@pytest.mark.asyncio
async def test_action_resource_admin_can_read_other_users_action(
    monkeypatch,
):
    user = make_user(
        username="admin",
        roles=["admin"],
    )

    class FakeAction:
        approval_id = "APR-OTHER1"
        action = "create_incident"
        requested_by = "it-support"
        state = "pending"
        payload_json = '{"title":"VPN issue"}'
        resource_id = None
        failure_reason = None
        result_json = None
        version = 1

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(
            self,
            exc_type,
            exc_value,
            traceback,
        ):
            return False

    def fake_session_local():
        return FakeSession()

    def fake_get_pending_action_for_user(
        *,
        session,
        approval_id,
        username,
        roles,
    ):
        assert approval_id == "APR-OTHER1"
        assert username == "admin"
        assert roles == ["admin"]

        return FakeAction()

    monkeypatch.setattr(
        ("ai_it_support_assistant.mcp_server.server.SessionLocal"),
        fake_session_local,
    )

    monkeypatch.setattr(
        ("ai_it_support_assistant.mcp_server.server.get_pending_action_for_user"),
        fake_get_pending_action_for_user,
    )

    server = create_mcp_server(
        current_user_provider=lambda: user,
    )

    async with Client(server) as client:
        resource = await client.read_resource("action://APR-OTHER1")

    assert resource is not None


@pytest.mark.asyncio
async def test_action_resource_non_owner_is_denied(
    monkeypatch,
):
    user = make_user(
        username="reader",
        roles=["reader"],
    )

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(
            self,
            exc_type,
            exc_value,
            traceback,
        ):
            return False

    def fake_session_local():
        return FakeSession()

    def fake_get_pending_action_for_user(
        *,
        session,
        approval_id,
        username,
        roles,
    ):
        raise PermissionError("Approval belongs to another user.")

    monkeypatch.setattr(
        ("ai_it_support_assistant.mcp_server.server.SessionLocal"),
        fake_session_local,
    )

    monkeypatch.setattr(
        ("ai_it_support_assistant.mcp_server.server.get_pending_action_for_user"),
        fake_get_pending_action_for_user,
    )

    server = create_mcp_server(
        current_user_provider=lambda: user,
    )

    async with Client(server) as client:
        with pytest.raises(MCPError):
            await client.read_resource("action://APR-OTHER1")


@pytest.mark.asyncio
async def test_mcp_server_registers_action_resource_template():
    user = make_user(
        username="it-support",
        roles=["it_support"],
    )

    server = create_mcp_server(
        current_user_provider=lambda: user,
    )

    async with Client(server) as client:
        result = await client.list_resource_templates()

    templates = {str(template.uri_template) for template in result.resource_templates}

    assert "action://{approval_id}" in templates


def test_mcp_kubernetes_state_checks_policy(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    user = make_user(
        username="alice",
        roles=["it_support"],
    )

    class FakeSession:
        pass

    fake_session = FakeSession()

    class FakeSessionContext:
        def __enter__(self):
            return fake_session

        def __exit__(
            self,
            exc_type,
            exc,
            traceback,
        ) -> None:
            return None

    def fake_session_local():
        return FakeSessionContext()

    def fake_authorize_kubernetes_read(
        *,
        subject,
        namespace,
        resource_type,
        resource_name,
        session,
    ) -> PolicyDecision:
        captured["username"] = subject.username
        captured["namespace"] = namespace
        captured["resource_type"] = resource_type
        captured["resource_name"] = resource_name
        captured["session"] = session

        return PolicyDecision(
            allowed=True,
            reason_code="allowed",
            reason="Kubernetes read allowed.",
            policy_id="kubernetes-read-v1",
            obligations=[],
        )

    def fake_get_kubernetes_resource_state(
        *,
        resource_type,
        name,
        namespace,
        config_mode,
        context,
    ):
        return {
            "resource_type": "deployment",
            "name": name,
            "namespace": namespace,
            "desired_replicas": 2,
            "ready_replicas": 2,
            "available_replicas": 2,
            "updated_replicas": 2,
        }

    monkeypatch.setattr(
        (
            "ai_it_support_assistant.mcp_server.server."
            "authorize_kubernetes_read"
        ),
        fake_authorize_kubernetes_read,
    )

    monkeypatch.setattr(
        (
            "ai_it_support_assistant.mcp_server.server."
            "get_kubernetes_resource_state"
        ),
        fake_get_kubernetes_resource_state,
    )

    monkeypatch.setattr(
        (
            "ai_it_support_assistant.mcp_server.server."
            "SessionLocal"
        ),
        fake_session_local,
    )

    server = create_mcp_server(
        current_user_provider=lambda: user,
    )

    async def run_test() -> None:
        async with Client(server) as client:
            result = await client.call_tool(
                "get_kubernetes_state",
                {
                    "resource_type": "deployment",
                    "resource_name": "api",
                    "namespace": "team-a-dev",
                },
            )

        assert result.is_error is False

    asyncio.run(run_test())

    assert captured["username"] == "alice"
    assert captured["namespace"] == "team-a-dev"
    assert captured["resource_type"] == "deployment"
    assert captured["resource_name"] == "api"
    assert captured["session"] is fake_session
import pytest

from ai_it_support_assistant.core.config import Settings


def require_safe_e2e_environment(
    settings: Settings,
) -> None:
    if not settings.e2e_enabled:
        raise RuntimeError("E2E testing is disabled.")

    if settings.environment != settings.e2e_expected_environment:
        raise RuntimeError("Unexpected E2E environment.")


def require_kubernetes_writes(
    settings: Settings,
) -> None:
    if not settings.e2e_kubernetes_writes_enabled:
        pytest.skip("E2E Kubernetes writes are disabled.")


def require_explicit_kubernetes_target(
    settings: Settings,
) -> tuple[str, str]:
    namespace = settings.e2e_test_namespace.strip()
    deployment = settings.e2e_test_deployment.strip()

    if not namespace:
        raise RuntimeError("E2E Kubernetes namespace is not configured.")

    if not deployment:
        raise RuntimeError("E2E Kubernetes deployment is not configured.")

    return namespace, deployment

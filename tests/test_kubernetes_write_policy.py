import pytest

from ai_it_support_assistant.services.kubernetes_write_policy_service import (
    KubernetesWritePolicyError,
    parse_csv_set,
    validate_restart_policy,
)


def test_parse_csv_set():
    result = parse_csv_set("dev, development , staging")

    assert result == {
        "dev",
        "development",
        "staging",
    }


def test_parse_csv_set_ignores_empty_values():
    result = parse_csv_set("dev,, ,development,")

    assert result == {
        "dev",
        "development",
    }


def test_restart_policy_rejects_when_writes_disabled():
    with pytest.raises(
        KubernetesWritePolicyError,
        match="Kubernetes writes are disabled",
    ):
        validate_restart_policy(
            namespace="dev",
            deployment_name="payment-api",
            write_enabled=False,
            allowed_namespaces_raw="dev",
            allowed_deployments_raw="payment-api",
        )


def test_restart_policy_rejects_namespace():
    with pytest.raises(
        KubernetesWritePolicyError,
        match="Namespace is not approved",
    ):
        validate_restart_policy(
            namespace="production",
            deployment_name="payment-api",
            write_enabled=True,
            allowed_namespaces_raw="dev",
            allowed_deployments_raw="payment-api",
        )


def test_restart_policy_rejects_deployment():
    with pytest.raises(
        KubernetesWritePolicyError,
        match="Deployment is not approved",
    ):
        validate_restart_policy(
            namespace="dev",
            deployment_name="identity-controller",
            write_enabled=True,
            allowed_namespaces_raw="dev",
            allowed_deployments_raw=("payment-api,vpn-api"),
        )


def test_restart_policy_allows_valid_target():
    validate_restart_policy(
        namespace="dev",
        deployment_name="payment-api",
        write_enabled=True,
        allowed_namespaces_raw="dev",
        allowed_deployments_raw="payment-api",
    )


def test_empty_namespace_allowlist_fails_closed():
    with pytest.raises(
        KubernetesWritePolicyError,
    ):
        validate_restart_policy(
            namespace="dev",
            deployment_name="payment-api",
            write_enabled=True,
            allowed_namespaces_raw="",
            allowed_deployments_raw="payment-api",
        )


def test_empty_deployment_allowlist_fails_closed():
    with pytest.raises(
        KubernetesWritePolicyError,
    ):
        validate_restart_policy(
            namespace="dev",
            deployment_name="payment-api",
            write_enabled=True,
            allowed_namespaces_raw="dev",
            allowed_deployments_raw="",
        )

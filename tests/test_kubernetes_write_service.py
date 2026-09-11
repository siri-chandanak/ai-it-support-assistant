from unittest.mock import MagicMock, patch

import pytest
from kubernetes.client.exceptions import ApiException

from ai_it_support_assistant.services.kubernetes_write_service import (
    KubernetesRestartAccessError,
    KubernetesRestartNotFoundError,
    KubernetesWriteError,
    deployment_has_restart_token,
    restart_deployment,
)


@patch("ai_it_support_assistant.services.kubernetes_write_service.get_apps_v1_api")
def test_restart_deployment_patches_restart_annotation(
    mock_get_apps_v1_api,
):
    api = MagicMock()
    mock_get_apps_v1_api.return_value = api

    restart_timestamp = "2026-09-11T08:30:00+00:00"

    restart_deployment(
        name="payment-api",
        namespace="dev",
        restart_timestamp=restart_timestamp,
        config_mode="local",
        context="dev-context",
    )

    api.patch_namespaced_deployment.assert_called_once_with(
        name="payment-api",
        namespace="dev",
        body={
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            ("kubectl.kubernetes.io/restartedAt"): restart_timestamp,
                        }
                    }
                }
            }
        },
    )


@patch("ai_it_support_assistant.services.kubernetes_write_service.get_apps_v1_api")
def test_restart_deployment_maps_404(
    mock_get_apps_v1_api,
):
    api = MagicMock()
    mock_get_apps_v1_api.return_value = api

    api.patch_namespaced_deployment.side_effect = ApiException(status=404)

    with pytest.raises(KubernetesRestartNotFoundError):
        restart_deployment(
            name="missing-api",
            namespace="dev",
            restart_timestamp="T1",
            config_mode="local",
            context="dev-context",
        )


@patch("ai_it_support_assistant.services.kubernetes_write_service.get_apps_v1_api")
def test_restart_deployment_maps_403(
    mock_get_apps_v1_api,
):
    api = MagicMock()
    mock_get_apps_v1_api.return_value = api

    api.patch_namespaced_deployment.side_effect = ApiException(status=403)

    with pytest.raises(KubernetesRestartAccessError):
        restart_deployment(
            name="payment-api",
            namespace="dev",
            restart_timestamp="T1",
            config_mode="local",
            context="dev-context",
        )


@patch("ai_it_support_assistant.services.kubernetes_write_service.get_apps_v1_api")
def test_restart_deployment_maps_generic_failure(
    mock_get_apps_v1_api,
):
    api = MagicMock()
    mock_get_apps_v1_api.return_value = api

    api.patch_namespaced_deployment.side_effect = ApiException(status=500)

    with pytest.raises(KubernetesWriteError):
        restart_deployment(
            name="payment-api",
            namespace="dev",
            restart_timestamp="T1",
            config_mode="local",
            context="dev-context",
        )


@patch("ai_it_support_assistant.services.kubernetes_write_service.get_apps_v1_api")
def test_deployment_has_restart_token_returns_true(
    mock_get_apps_v1_api,
):
    api = MagicMock()
    mock_get_apps_v1_api.return_value = api

    deployment = MagicMock()

    deployment.spec.template.metadata.annotations = {"kubectl.kubernetes.io/restartedAt": "T1"}

    api.read_namespaced_deployment.return_value = deployment

    result = deployment_has_restart_token(
        name="payment-api",
        namespace="dev",
        restart_timestamp="T1",
        config_mode="local",
        context="dev-context",
    )

    assert result is True


@patch("ai_it_support_assistant.services.kubernetes_write_service.get_apps_v1_api")
def test_deployment_has_restart_token_returns_false(
    mock_get_apps_v1_api,
):
    api = MagicMock()
    mock_get_apps_v1_api.return_value = api

    deployment = MagicMock()

    deployment.spec.template.metadata.annotations = {"kubectl.kubernetes.io/restartedAt": "T2"}

    api.read_namespaced_deployment.return_value = deployment

    result = deployment_has_restart_token(
        name="payment-api",
        namespace="dev",
        restart_timestamp="T1",
        config_mode="local",
        context="dev-context",
    )

    assert result is False


@patch("ai_it_support_assistant.services.kubernetes_write_service.get_apps_v1_api")
def test_deployment_without_annotations_has_no_token(
    mock_get_apps_v1_api,
):
    api = MagicMock()
    mock_get_apps_v1_api.return_value = api

    deployment = MagicMock()

    deployment.spec.template.metadata.annotations = None

    api.read_namespaced_deployment.return_value = deployment

    result = deployment_has_restart_token(
        name="payment-api",
        namespace="dev",
        restart_timestamp="T1",
        config_mode="local",
        context="dev-context",
    )

    assert result is False

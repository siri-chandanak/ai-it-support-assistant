from kubernetes.client.exceptions import ApiException

from ai_it_support_assistant.services.kubernetes_client_service import (
    get_apps_v1_api,
)

RESTART_ANNOTATION = "kubectl.kubernetes.io/restartedAt"


class KubernetesWriteError(Exception):
    pass


class KubernetesRestartNotFoundError(KubernetesWriteError):
    pass


class KubernetesRestartAccessError(KubernetesWriteError):
    pass


def restart_deployment(
    *,
    name: str,
    namespace: str,
    restart_timestamp: str,
    config_mode: str,
    context: str,
) -> None:
    api = get_apps_v1_api(
        config_mode=config_mode,
        context=context,
    )

    body = {
        "spec": {
            "template": {
                "metadata": {
                    "annotations": {
                        RESTART_ANNOTATION: restart_timestamp,
                    }
                }
            }
        }
    }

    try:
        api.patch_namespaced_deployment(
            name=name,
            namespace=namespace,
            body=body,
        )

    except ApiException as exc:
        if exc.status == 404:
            raise KubernetesRestartNotFoundError("Deployment was not found.") from exc

        if exc.status == 403:
            raise KubernetesRestartAccessError("Kubernetes denied deployment restart.") from exc

        raise KubernetesWriteError("Deployment restart failed.") from exc


def deployment_has_restart_token(
    *,
    name: str,
    namespace: str,
    restart_timestamp: str,
    config_mode: str,
    context: str,
) -> bool:
    api = get_apps_v1_api(
        config_mode=config_mode,
        context=context,
    )

    try:
        deployment = api.read_namespaced_deployment(
            name=name,
            namespace=namespace,
        )

    except ApiException as exc:
        if exc.status == 404:
            raise KubernetesRestartNotFoundError("Deployment was not found.") from exc

        if exc.status == 403:
            raise KubernetesRestartAccessError("Kubernetes denied deployment read.") from exc

        raise KubernetesWriteError("Failed to read Deployment.") from exc

    annotations = deployment.spec.template.metadata.annotations or {}

    return annotations.get(RESTART_ANNOTATION) == restart_timestamp

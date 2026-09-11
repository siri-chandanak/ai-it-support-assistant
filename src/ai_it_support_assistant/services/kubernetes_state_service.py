from kubernetes.client.exceptions import ApiException

from ai_it_support_assistant.schemas.kubernetes import (
    DeploymentState,
    PodState,
)
from ai_it_support_assistant.services.kubernetes_client_service import (
    get_apps_v1_api,
    get_core_v1_api,
)


class KubernetesStateError(Exception):
    pass


class KubernetesResourceNotFoundError(KubernetesStateError):
    pass


class KubernetesAccessError(KubernetesStateError):
    pass


def get_deployment_state(
    *,
    name: str,
    namespace: str,
    config_mode: str,
    context: str,
) -> DeploymentState:
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
            raise KubernetesResourceNotFoundError("Deployment was not found.") from exc

        if exc.status == 403:
            raise KubernetesAccessError("Kubernetes access was denied.") from exc

        raise KubernetesStateError("Failed to read deployment state.") from exc

    status = deployment.status

    generation = deployment.metadata.generation or 0
    observed_generation = status.observed_generation or 0

    conditions = status.conditions or []

    progress_deadline_exceeded = any(
        (
            condition.type == "Progressing"
            and condition.status == "False"
            and condition.reason == "ProgressDeadlineExceeded"
        )
        for condition in conditions
    )

    return DeploymentState(
        name=name,
        namespace=namespace,
        desired_replicas=(deployment.spec.replicas or 0),
        ready_replicas=(status.ready_replicas or 0),
        available_replicas=(status.available_replicas or 0),
        updated_replicas=(status.updated_replicas or 0),
        generation=generation,
        observed_generation=observed_generation,
        progress_deadline_exceeded=progress_deadline_exceeded,
    )


def get_pod_state(
    *,
    name: str,
    namespace: str,
    config_mode: str,
    context: str,
) -> PodState:
    api = get_core_v1_api(
        config_mode=config_mode,
        context=context,
    )

    try:
        pod = api.read_namespaced_pod(
            name=name,
            namespace=namespace,
        )

    except ApiException as exc:
        if exc.status == 404:
            raise KubernetesResourceNotFoundError("Pod was not found.") from exc

        if exc.status == 403:
            raise KubernetesAccessError("Kubernetes access was denied.") from exc

        raise KubernetesStateError("Failed to read pod state.") from exc

    container_statuses = pod.status.container_statuses or []

    ready = bool(container_statuses) and all(container.ready for container in container_statuses)

    restart_count = sum(container.restart_count for container in container_statuses)

    return PodState(
        name=name,
        namespace=namespace,
        phase=pod.status.phase or "Unknown",
        ready=ready,
        restart_count=restart_count,
    )


def get_kubernetes_resource_state(
    *,
    resource_type: str,
    name: str,
    namespace: str,
    config_mode: str,
    context: str,
) -> DeploymentState | PodState:
    if resource_type == "deployment":
        return get_deployment_state(
            name=name,
            namespace=namespace,
            config_mode=config_mode,
            context=context,
        )

    if resource_type == "pod":
        return get_pod_state(
            name=name,
            namespace=namespace,
            config_mode=config_mode,
            context=context,
        )

    raise KubernetesStateError("Unsupported Kubernetes resource type.")


def is_deployment_rollout_healthy(
    state: DeploymentState,
) -> bool:
    desired = state.desired_replicas

    if desired <= 0:
        return False

    return all(
        [
            state.observed_generation >= state.generation,
            state.updated_replicas == desired,
            state.ready_replicas == desired,
            state.available_replicas == desired,
        ]
    )

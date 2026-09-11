import logging
import time

from ai_it_support_assistant.core.request_context import get_request_id
from ai_it_support_assistant.schemas.kubernetes import DeploymentRolloutResult
from ai_it_support_assistant.services.kubernetes_state_service import (
    KubernetesResourceNotFoundError,
    KubernetesStateError,
    get_deployment_state,
    is_deployment_rollout_healthy,
)

logger = logging.getLogger(__name__)


def monitor_deployment_rollout(
    *,
    name: str,
    namespace: str,
    timeout_seconds: int,
    poll_interval_seconds: int,
    max_read_failures: int,
    config_mode: str,
    context: str,
) -> DeploymentRolloutResult:
    if timeout_seconds <= 0:
        raise ValueError("Rollout timeout must be positive.")

    if poll_interval_seconds <= 0:
        raise ValueError("Rollout poll interval must be positive.")

    if poll_interval_seconds > timeout_seconds:
        raise ValueError("Poll interval cannot exceed timeout.")

    if max_read_failures <= 0:
        raise ValueError("Maximum read failures must be positive.")

    deadline = time.monotonic() + timeout_seconds
    consecutive_failures = 0

    while True:
        try:
            state = get_deployment_state(
                name=name,
                namespace=namespace,
                config_mode=config_mode,
                context=context,
            )

            consecutive_failures = 0

        except KubernetesResourceNotFoundError:
            raise

        except KubernetesStateError:
            consecutive_failures += 1

            logger.warning(
                (
                    "deployment_rollout_read_failed "
                    "request_id=%s "
                    "namespace=%s "
                    "deployment=%s "
                    "consecutive_failures=%s"
                ),
                get_request_id(),
                namespace,
                name,
                consecutive_failures,
            )

            if consecutive_failures >= max_read_failures:
                return DeploymentRolloutResult(
                    deployment_name=name,
                    namespace=namespace,
                    outcome="failed",
                    desired_replicas=0,
                    updated_replicas=0,
                    ready_replicas=0,
                    available_replicas=0,
                    message=("Unable to reliably read Deployment state while monitoring rollout."),
                )

            if time.monotonic() >= deadline:
                return DeploymentRolloutResult(
                    deployment_name=name,
                    namespace=namespace,
                    outcome="timeout",
                    desired_replicas=0,
                    updated_replicas=0,
                    ready_replicas=0,
                    available_replicas=0,
                    message=("Deployment rollout monitoring timed out."),
                )

            time.sleep(poll_interval_seconds)
            continue

        logger.info(
            (
                "deployment_rollout_polled "
                "request_id=%s "
                "namespace=%s "
                "deployment=%s "
                "desired=%s "
                "updated=%s "
                "ready=%s "
                "available=%s "
                "generation=%s "
                "observed_generation=%s"
            ),
            get_request_id(),
            namespace,
            name,
            state.desired_replicas,
            state.updated_replicas,
            state.ready_replicas,
            state.available_replicas,
            state.generation,
            state.observed_generation,
        )

        if state.progress_deadline_exceeded:
            return DeploymentRolloutResult(
                deployment_name=name,
                namespace=namespace,
                outcome="failed",
                desired_replicas=state.desired_replicas,
                updated_replicas=state.updated_replicas,
                ready_replicas=state.ready_replicas,
                available_replicas=state.available_replicas,
                message=("Deployment exceeded its Kubernetes progress deadline."),
            )

        if is_deployment_rollout_healthy(state):
            return DeploymentRolloutResult(
                deployment_name=name,
                namespace=namespace,
                outcome="healthy",
                desired_replicas=state.desired_replicas,
                updated_replicas=state.updated_replicas,
                ready_replicas=state.ready_replicas,
                available_replicas=state.available_replicas,
                message=("Deployment rollout completed successfully."),
            )

        if time.monotonic() >= deadline:
            return DeploymentRolloutResult(
                deployment_name=name,
                namespace=namespace,
                outcome="timeout",
                desired_replicas=state.desired_replicas,
                updated_replicas=state.updated_replicas,
                ready_replicas=state.ready_replicas,
                available_replicas=state.available_replicas,
                message=("Deployment rollout did not become healthy before timeout."),
            )

        time.sleep(poll_interval_seconds)

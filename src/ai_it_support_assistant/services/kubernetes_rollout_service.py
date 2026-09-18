import logging
import time
from collections.abc import Callable

from opentelemetry.trace import Status, StatusCode

from ai_it_support_assistant.core.request_context import get_request_id
from ai_it_support_assistant.observability.tracing import get_tracer
from ai_it_support_assistant.schemas.kubernetes import DeploymentRolloutResult
from ai_it_support_assistant.services.kubernetes_client_service import (
    get_apps_v1_api,
)
from ai_it_support_assistant.services.kubernetes_state_service import (
    KubernetesResourceNotFoundError,
    KubernetesStateError,
    get_deployment_state,
    is_deployment_rollout_healthy,
)

logger = logging.getLogger(__name__)

tracer = get_tracer()

RESTARTED_AT_ANNOTATION = "kubectl.kubernetes.io/restartedAt"


def monitor_deployment_rollout(
    *,
    name: str,
    namespace: str,
    timeout_seconds: int,
    poll_interval_seconds: int,
    max_read_failures: int,
    config_mode: str,
    context: str,
    heartbeat_callback: Callable[[], None] | None = None,
) -> DeploymentRolloutResult:
    if timeout_seconds <= 0:
        raise ValueError("Rollout timeout must be positive.")

    if poll_interval_seconds <= 0:
        raise ValueError("Rollout poll interval must be positive.")

    if poll_interval_seconds > timeout_seconds:
        raise ValueError("Poll interval cannot exceed timeout.")

    if max_read_failures <= 0:
        raise ValueError("Maximum read failures must be positive.")

    with tracer.start_as_current_span("kubernetes.rollout.monitor") as span:
        span.set_attribute(
            "kubernetes.resource_type",
            "deployment",
        )
        span.set_attribute(
            "rollout.timeout_seconds",
            timeout_seconds,
        )
        span.set_attribute(
            "rollout.poll_interval_seconds",
            poll_interval_seconds,
        )
        span.set_attribute(
            "rollout.max_read_failures",
            max_read_failures,
        )

        try:
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
                    if heartbeat_callback is not None:
                        heartbeat_callback()

                    span.set_attribute(
                        "rollout.outcome",
                        "resource_not_found",
                    )
                    span.set_attribute(
                        "rollout.failure_reason",
                        "resource_not_found",
                    )

                    raise

                except KubernetesStateError as exc:
                    consecutive_failures += 1

                    if heartbeat_callback is not None:
                        heartbeat_callback()

                    span.add_event(
                        "rollout_read_failed",
                        {
                            "consecutive_failures": consecutive_failures,
                        },
                    )

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
                        span.record_exception(exc)

                        span.set_attribute(
                            "rollout.outcome",
                            "failed",
                        )
                        span.set_attribute(
                            "rollout.failure_reason",
                            "max_read_failures",
                        )

                        span.set_status(
                            Status(
                                StatusCode.ERROR,
                                "Unable to reliably read Deployment state.",
                            )
                        )

                        return DeploymentRolloutResult(
                            deployment_name=name,
                            namespace=namespace,
                            outcome="failed",
                            desired_replicas=0,
                            updated_replicas=0,
                            ready_replicas=0,
                            available_replicas=0,
                            message=(
                                "Unable to reliably read Deployment state while monitoring rollout."
                            ),
                        )

                    if time.monotonic() >= deadline:
                        span.set_attribute(
                            "rollout.outcome",
                            "timeout",
                        )
                        span.set_attribute(
                            "rollout.failure_reason",
                            "read_timeout",
                        )

                        span.add_event(
                            "rollout_timeout",
                            {
                                "reason": "read_timeout",
                            },
                        )

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

                if heartbeat_callback is not None:
                    heartbeat_callback()

                span.add_event(
                    "rollout_poll",
                    {
                        "desired_replicas": state.desired_replicas,
                        "updated_replicas": state.updated_replicas,
                        "ready_replicas": state.ready_replicas,
                        "available_replicas": state.available_replicas,
                        "generation": state.generation,
                        "observed_generation": (state.observed_generation),
                        "consecutive_failures": (consecutive_failures),
                    },
                )

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
                    span.set_attribute(
                        "rollout.outcome",
                        "failed",
                    )
                    span.set_attribute(
                        "rollout.failure_reason",
                        "progress_deadline_exceeded",
                    )

                    span.add_event("rollout_progress_deadline_exceeded")

                    return DeploymentRolloutResult(
                        deployment_name=name,
                        namespace=namespace,
                        outcome="failed",
                        desired_replicas=(state.desired_replicas),
                        updated_replicas=(state.updated_replicas),
                        ready_replicas=(state.ready_replicas),
                        available_replicas=(state.available_replicas),
                        message=("Deployment exceeded its Kubernetes progress deadline."),
                    )

                if is_deployment_rollout_healthy(state):
                    span.set_attribute(
                        "rollout.outcome",
                        "healthy",
                    )

                    span.add_event(
                        "rollout_healthy",
                        {
                            "desired_replicas": (state.desired_replicas),
                            "ready_replicas": (state.ready_replicas),
                            "available_replicas": (state.available_replicas),
                        },
                    )

                    return DeploymentRolloutResult(
                        deployment_name=name,
                        namespace=namespace,
                        outcome="healthy",
                        desired_replicas=(state.desired_replicas),
                        updated_replicas=(state.updated_replicas),
                        ready_replicas=(state.ready_replicas),
                        available_replicas=(state.available_replicas),
                        message=("Deployment rollout completed successfully."),
                    )

                if time.monotonic() >= deadline:
                    span.set_attribute(
                        "rollout.outcome",
                        "timeout",
                    )
                    span.set_attribute(
                        "rollout.failure_reason",
                        "rollout_timeout",
                    )

                    span.add_event(
                        "rollout_timeout",
                        {
                            "desired_replicas": (state.desired_replicas),
                            "updated_replicas": (state.updated_replicas),
                            "ready_replicas": (state.ready_replicas),
                            "available_replicas": (state.available_replicas),
                        },
                    )

                    return DeploymentRolloutResult(
                        deployment_name=name,
                        namespace=namespace,
                        outcome="timeout",
                        desired_replicas=(state.desired_replicas),
                        updated_replicas=(state.updated_replicas),
                        ready_replicas=(state.ready_replicas),
                        available_replicas=(state.available_replicas),
                        message=("Deployment rollout did not become healthy before timeout."),
                    )

                time.sleep(poll_interval_seconds)

        except Exception as exc:
            span.record_exception(exc)

            span.set_status(
                Status(
                    StatusCode.ERROR,
                    "Deployment rollout monitoring failed.",
                )
            )

            raise


def get_deployment_restart_token(
    *,
    name: str,
    namespace: str,
    config_mode: str,
    context: str | None,
) -> str | None:
    with tracer.start_as_current_span("kubernetes.read_restart_token") as span:
        span.set_attribute(
            "kubernetes.resource_type",
            "deployment",
        )

        try:
            apps_api = get_apps_v1_api(
                config_mode=config_mode,
                context=context,
            )

            deployment = apps_api.read_namespaced_deployment(
                name=name,
                namespace=namespace,
            )

            annotations = deployment.spec.template.metadata.annotations or {}

            restart_token = annotations.get(RESTARTED_AT_ANNOTATION)

            span.set_attribute(
                "restart.token_present",
                restart_token is not None,
            )

            return restart_token

        except Exception as exc:
            span.record_exception(exc)

            span.set_status(
                Status(
                    StatusCode.ERROR,
                    "Failed to read Deployment restart token.",
                )
            )

            raise

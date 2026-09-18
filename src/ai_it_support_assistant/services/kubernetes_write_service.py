import time

from kubernetes.client.exceptions import ApiException
from opentelemetry.trace import Status, StatusCode

from ai_it_support_assistant.observability.metrics import (
    DEPLOYMENT_RESTART_DURATION,
    KUBERNETES_WRITE_ATTEMPTS,
    KUBERNETES_WRITE_FAILURES,
)
from ai_it_support_assistant.observability.tracing import get_tracer
from ai_it_support_assistant.services.kubernetes_client_service import (
    get_apps_v1_api,
)

RESTART_ANNOTATION = "kubectl.kubernetes.io/restartedAt"

tracer = get_tracer()


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
    start_time = time.perf_counter()

    KUBERNETES_WRITE_ATTEMPTS.labels(
        operation="restart_deployment",
    ).inc()

    with tracer.start_as_current_span("kubernetes.restart") as span:
        span.set_attribute(
            "kubernetes.resource_type",
            "deployment",
        )

        try:
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

            api.patch_namespaced_deployment(
                name=name,
                namespace=namespace,
                body=body,
            )

            span.add_event("restart_patch_applied")

        except ApiException as exc:
            span.record_exception(exc)

            span.set_status(
                Status(
                    StatusCode.ERROR,
                    "Kubernetes restart failed",
                )
            )

            if exc.status == 404:
                reason = "not_found"

            elif exc.status == 403:
                reason = "access_denied"

            else:
                reason = "api_error"

            KUBERNETES_WRITE_FAILURES.labels(
                operation="restart_deployment",
                reason=reason,
            ).inc()

            if exc.status == 404:
                raise KubernetesRestartNotFoundError("Deployment was not found.") from exc

            if exc.status == 403:
                raise KubernetesRestartAccessError("Kubernetes denied deployment restart.") from exc

            raise KubernetesWriteError("Deployment restart failed.") from exc

        finally:
            DEPLOYMENT_RESTART_DURATION.observe(time.perf_counter() - start_time)


def deployment_has_restart_token(
    *,
    name: str,
    namespace: str,
    restart_timestamp: str,
    config_mode: str,
    context: str,
) -> bool:
    with tracer.start_as_current_span("kubernetes.verify_restart") as span:
        span.set_attribute(
            "kubernetes.resource_type",
            "deployment",
        )

        try:
            api = get_apps_v1_api(
                config_mode=config_mode,
                context=context,
            )

            deployment = api.read_namespaced_deployment(
                name=name,
                namespace=namespace,
            )

        except ApiException as exc:
            span.record_exception(exc)
            span.set_status(
                Status(
                    StatusCode.ERROR,
                    "Kubernetes restart verification failed",
                )
            )

            if exc.status == 404:
                raise KubernetesRestartNotFoundError("Deployment was not found.") from exc

            if exc.status == 403:
                raise KubernetesRestartAccessError("Kubernetes denied deployment read.") from exc

            raise KubernetesWriteError("Failed to read Deployment.") from exc

        annotations = deployment.spec.template.metadata.annotations or {}

        verified = annotations.get(RESTART_ANNOTATION) == restart_timestamp

        span.set_attribute(
            "restart.verified",
            verified,
        )

        if verified:
            span.add_event("restart_verified")
        else:
            span.add_event("restart_not_verified")

        return verified

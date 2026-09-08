from kubernetes import client, config

from ai_it_support_assistant.core.config import get_settings
from ai_it_support_assistant.schemas.agent import AgentDecision
from ai_it_support_assistant.services.kubernetes_state_service import (
    get_deployment_state,
    get_kubernetes_resource_state,
    get_pod_state,
)

settings = get_settings()

print(settings.kubernetes_config_mode)
print(settings.kubernetes_context)
print(settings.kubernetes_default_namespace)

config.load_kube_config()

core = client.CoreV1Api()

result = core.list_namespace()

for namespace in result.items:
    print(namespace.metadata.name)

apps = client.AppsV1Api()

result = apps.list_namespaced_deployment(namespace="ai-it-support-test")

for deployment in result.items:
    print(deployment.metadata.name)


decision = AgentDecision(
    action="kubernetes_state",
    service_name=None,
    kubernetes_resource_type="deployment",
    kubernetes_resource_name="demo-api",
    kubernetes_namespace="ai-it-support-test",
    reasoning_summary="Current Deployment state requested.",
)

print("Decision: ", decision)

state = get_deployment_state(
    name="demo-api",
    namespace="ai-it-support-test",
    config_mode="local",
    context="kind-kin",
)

print(state)

state = get_pod_state(
    name="demo-worker",
    namespace="ai-it-support-test",
    config_mode="local",
    context="kind-kin",
)

print(state)

state = get_kubernetes_resource_state(
    resource_type="deployment",
    name="demo-api",
    namespace="ai-it-support-test",
    config_mode="local",
    context="kind-kin",
)

print(state)

class KubernetesWritePolicyError(Exception):
    pass


def parse_csv_set(raw_value: str) -> set[str]:
    return {value.strip() for value in raw_value.split(",") if value.strip()}


def validate_restart_policy(
    *,
    namespace: str,
    deployment_name: str,
    write_enabled: bool,
    allowed_namespaces_raw: str,
    allowed_deployments_raw: str,
) -> None:
    if not write_enabled:
        raise KubernetesWritePolicyError("Kubernetes writes are disabled.")

    allowed_namespaces = parse_csv_set(allowed_namespaces_raw)

    if namespace not in allowed_namespaces:
        raise KubernetesWritePolicyError("Namespace is not approved.")

    allowed_deployments = parse_csv_set(allowed_deployments_raw)

    if deployment_name not in allowed_deployments:
        raise KubernetesWritePolicyError("Deployment is not approved.")

from ai_it_support_assistant.schemas.policy import (
    PolicyContext,
    PolicyRequest,
)


def _parse_csv_values(
    raw_value: str,
) -> list[str]:
    return sorted({value.strip() for value in raw_value.split(",") if value.strip()})


class PolicyContextService:
    def __init__(
        self,
        *,
        settings,
        resource_permission_repository,
    ) -> None:
        self.settings = settings
        self.resource_permission_repository = resource_permission_repository

    def enrich(
        self,
        *,
        request: PolicyRequest,
        session,
    ) -> PolicyRequest:
        attributes = dict(request.context.attributes)

        if request.action == "deployment.restart":
            namespace = request.resource.attributes.get("namespace")

            attributes.setdefault(
                "allowed_namespaces",
                _parse_csv_values(self.settings.kubernetes_restart_allowed_namespaces),
            )

            attributes.setdefault(
                "allowed_deployments",
                _parse_csv_values(self.settings.kubernetes_restart_allowed_deployments),
            )

            attributes.setdefault(
                "writes_enabled",
                self.settings.kubernetes_write_enabled,
            )

            if "has_namespace_grant" not in attributes:
                attributes["has_namespace_grant"] = (
                    self.resource_permission_repository.has_permission(
                        session=session,
                        username=request.subject.username,
                        permission="deployment:restart",
                        resource_type="namespace",
                        resource_value=namespace,
                    )
                )

        if request.action == "kubernetes.read":
            namespace = request.resource.attributes.get("namespace")

            attributes["has_namespace_grant"] = self.resource_permission_repository.has_permission(
                session=session,
                username=(request.subject.username),
                permission="kubernetes:read",
                resource_type="namespace",
                resource_value=namespace,
            )

        return request.model_copy(
            update={
                "context": PolicyContext(
                    attributes=attributes,
                )
            }
        )

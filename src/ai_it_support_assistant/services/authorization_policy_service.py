from sqlalchemy.orm import Session

from ai_it_support_assistant.schemas.auth import User
from ai_it_support_assistant.services.permission_service import (
    require_permission,
)
from ai_it_support_assistant.services.resource_authorization_service import (
    require_namespace_permission,
)


def authorize_deployment_restart(
    *,
    user: User,
    namespace: str,
    session: Session,
) -> None:
    require_permission(
        user=user,
        permission="deployment:restart",
    )

    require_namespace_permission(
        user=user,
        permission="deployment:restart",
        namespace=namespace,
        session=session,
    )

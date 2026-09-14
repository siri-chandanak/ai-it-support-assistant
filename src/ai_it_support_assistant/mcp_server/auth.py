from mcp.server.auth.provider import AccessToken, TokenVerifier

from ai_it_support_assistant.core.config import get_settings
from ai_it_support_assistant.services.auth_service import (
    AuthenticationError,
    decode_access_token,
)


class ApplicationTokenVerifier(TokenVerifier):
    async def verify_token(
        self,
        token: str,
    ) -> AccessToken | None:
        settings = get_settings()

        try:
            token_data = decode_access_token(
                token=token,
                secret_key=settings.jwt_secret_key,
                algorithm=settings.jwt_algorithm,
            )
        except AuthenticationError:
            return None

        return AccessToken(
            token=token,
            client_id="ai-it-support-client",
            subject=str(token_data.user_id),
            scopes=[],
            claims={},
        )

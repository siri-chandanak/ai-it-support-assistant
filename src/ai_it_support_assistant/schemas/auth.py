from uuid import UUID

from pydantic import BaseModel, Field


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    user_id: UUID | None = None


class User(BaseModel):
    user_id: UUID
    username: str

    roles: list[str] = Field(
        default_factory=list,
    )

    disabled: bool = False

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, create_model


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=255)


class AuthUserRead(BaseModel):
    id: int
    username: str
    display_name: str
    email: str
    last_login_at: Optional[datetime]

    model_config = {"from_attributes": True}


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=255)
    new_password: str = Field(min_length=8, max_length=255)
    confirm_new_password: str = Field(min_length=8, max_length=255)

_COMPAT_SCHEMA_NAMES = {
    "AccountProfileRead",
    "SessionInfoRead",
    "SessionListRead",
    "AccessTokenCreateRequest",
    "AccessTokenCreateRead",
    "AccessTokenInfoRead",
    "AccessTokenListRead",
}


def _create_compat_schema(name: str) -> type[BaseModel]:
    module_name = __name__
    if name == "AccountProfileRead":
        model = create_model(
            name,
            __module__=module_name,
            id=(int, ...),
            username=(str, ...),
            created_at=(datetime, ...),
            password_changed_at=(datetime, ...),
            last_login_at=(Optional[datetime], ...),
            api_token_enabled=(bool, ...),
            mcp_enabled=(bool, ...),
        )
        model.model_config = {"from_attributes": True}
        return model
    if name == "SessionInfoRead":
        return create_model(
            name,
            __module__=module_name,
            id=(int, ...),
            created_at=(datetime, ...),
            expires_at=(datetime, ...),
            last_seen_at=(datetime, ...),
            is_current=(bool, ...),
        )
    if name == "SessionListRead":
        session_info = __getattr__("SessionInfoRead")
        return create_model(
            name,
            __module__=module_name,
            items=(list[session_info], ...),
        )
    if name == "AccessTokenCreateRequest":
        return create_model(
            name,
            __module__=module_name,
            name=(str, Field(min_length=1, max_length=200)),
            token_type=(str, Field(pattern="^(api|mcp)$")),
            password=(str, Field(min_length=1, max_length=255)),
            expires_in_days=(Optional[int], Field(default=None, ge=1, le=365)),
            expires_in_seconds=(Optional[int], Field(default=None, ge=0, le=31_536_000)),
        )
    if name == "AccessTokenCreateRead":
        return create_model(
            name,
            __module__=module_name,
            id=(int, ...),
            name=(str, ...),
            token_type=(str, ...),
            token=(str, ...),
            created_at=(datetime, ...),
            expires_at=(Optional[datetime], ...),
            api_base_url=(Optional[str], None),
            mcp_url=(Optional[str], None),
        )
    if name == "AccessTokenInfoRead":
        return create_model(
            name,
            __module__=module_name,
            id=(int, ...),
            name=(str, ...),
            token_type=(str, ...),
            created_at=(datetime, ...),
            expires_at=(Optional[datetime], ...),
            last_seen_at=(Optional[datetime], ...),
        )
    if name == "AccessTokenListRead":
        access_token_info = __getattr__("AccessTokenInfoRead")
        return create_model(
            name,
            __module__=module_name,
            items=(list[access_token_info], ...),
        )
    raise AttributeError(name)


def __getattr__(name: str):
    if name not in _COMPAT_SCHEMA_NAMES:
        raise AttributeError(name)
    schema = _create_compat_schema(name)
    globals()[name] = schema
    return schema

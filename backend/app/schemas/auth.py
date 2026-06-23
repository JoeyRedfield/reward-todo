from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=255)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=200)
    display_name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=255)
    confirm_password: str = Field(min_length=8, max_length=255)
    create_default_workspace: bool = True

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip()
        if any(character.isspace() for character in normalized):
            raise ValueError("Invalid email address")
        if normalized.count("@") != 1:
            raise ValueError("Invalid email address")
        local_part, domain = normalized.split("@", 1)
        if not local_part or not domain:
            raise ValueError("Invalid email address")
        if "." not in domain or domain.startswith(".") or domain.endswith(".") or ".." in domain:
            raise ValueError("Invalid email address")
        return normalized

    @field_validator("username", "display_name")
    @classmethod
    def validate_non_blank_text(cls, value: str) -> str:
        if value.strip() == "":
            raise ValueError("Value cannot be blank")
        return value


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


class AccountProfileRead(BaseModel):
    id: int
    username: str
    display_name: str
    email: str
    created_at: datetime
    password_changed_at: datetime
    last_login_at: Optional[datetime]
    api_token_enabled: bool
    mcp_enabled: bool

    model_config = {"from_attributes": True}


class SessionInfoRead(BaseModel):
    id: int
    created_at: datetime
    expires_at: datetime
    last_seen_at: datetime
    is_current: bool


class SessionListRead(BaseModel):
    items: list[SessionInfoRead]


class AccessTokenCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    token_type: str = Field(pattern="^(api|mcp)$")
    password: str = Field(min_length=1, max_length=255)
    expires_in_days: Optional[int] = Field(default=None, ge=1, le=365)
    expires_in_seconds: Optional[int] = Field(default=None, ge=0, le=31_536_000)


class AccessTokenCreateRead(BaseModel):
    id: int
    name: str
    token_type: str
    token: str
    created_at: datetime
    expires_at: Optional[datetime]
    api_base_url: Optional[str] = None
    mcp_url: Optional[str] = None


class AccessTokenInfoRead(BaseModel):
    id: int
    name: str
    token_type: str
    created_at: datetime
    expires_at: Optional[datetime]
    last_seen_at: Optional[datetime]


class AccessTokenListRead(BaseModel):
    items: list[AccessTokenInfoRead]

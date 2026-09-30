from uuid import UUID

from pydantic import EmailStr, Field

from app.core.permissions import Role
from app.schemas.base import APIModel


class LoginRequest(APIModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class PasswordChangeRequest(APIModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=15, max_length=128)


class UserResponse(APIModel):
    id: UUID
    email: str | None
    display_name: str
    role: Role
    is_disabled: bool = False


class UserCreate(APIModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=160)
    password: str = Field(min_length=15, max_length=128)
    role: Role = Role.VIEWER


class UserUpdate(APIModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=160)
    role: Role | None = None
    is_disabled: bool | None = None
    password: str | None = Field(default=None, min_length=15, max_length=128)

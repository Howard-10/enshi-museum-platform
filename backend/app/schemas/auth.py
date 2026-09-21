from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class AuthCredentials(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)


class RegisterRequest(AuthCredentials):
    display_name: str = Field(min_length=1, max_length=100)


class AuthUserRead(BaseModel):
    id: UUID
    email: str
    display_name: str
    role: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: AuthUserRead

from __future__ import annotations

from pydantic import Field

from app.schemas.base import SchemaBase


class RequestCodeIn(SchemaBase):
    email: str


class VerifyCodeIn(SchemaBase):
    email: str
    code: str
    name: str | None = None


class GoogleSignInIn(SchemaBase):
    id_token: str


class GoogleCodeSignInIn(SchemaBase):
    code: str = Field(min_length=1, max_length=2048)
    redirect_uri: str | None = None
    state: str = Field(min_length=1, max_length=4096)

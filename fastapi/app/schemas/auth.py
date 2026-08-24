from __future__ import annotations

from pydantic import Field

from app.schemas.base import SchemaBase


class RequestCodeIn(SchemaBase):
    email: str = Field(min_length=3, max_length=254)


class VerifyCodeIn(SchemaBase):
    email: str = Field(min_length=3, max_length=254)
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    name: str | None = Field(default=None, max_length=120)


class GoogleSignInIn(SchemaBase):
    id_token: str


class GoogleCodeSignInIn(SchemaBase):
    code: str = Field(min_length=1, max_length=2048)
    redirect_uri: str | None = None
    state: str = Field(min_length=1, max_length=4096)

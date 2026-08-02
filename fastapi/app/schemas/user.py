from __future__ import annotations

from typing import Optional

from app.models.enums import Role
from app.schemas.base import SchemaBase


class UserOut(SchemaBase):
    id: str
    email: str
    name: Optional[str] = None
    phone: Optional[str] = None
    role: Role
    image: Optional[str] = None


class TokenOut(SchemaBase):
    user: UserOut

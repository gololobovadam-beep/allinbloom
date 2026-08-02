from __future__ import annotations

from sqlalchemy import Column, DateTime, Enum, Integer, String, func

from app.core.database import Base
from app.models.enums import Role
from app.utils.ids import generate_cuid


class User(Base):
    __tablename__ = "User"

    id = Column(String, primary_key=True, default=generate_cuid)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    role = Column(Enum(Role, name="Role"), default=Role.CUSTOMER, nullable=False)
    image = Column(String, nullable=True)
    auth_version = Column("authVersion", Integer, nullable=False, default=0, server_default="0")
    created_at = Column(
        "createdAt", DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        "updatedAt",
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

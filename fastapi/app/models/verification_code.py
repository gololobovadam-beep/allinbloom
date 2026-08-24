from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, String, func

from app.core.database import Base
from app.utils.ids import generate_cuid


class VerificationCode(Base):
    __tablename__ = "VerificationCode"

    id = Column(String, primary_key=True, default=generate_cuid)
    email = Column(String, nullable=False, index=True)
    code_hash = Column("codeHash", String, nullable=False)
    salt = Column(String, nullable=False)
    attempt_count = Column(
        "attemptCount",
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    expires_at = Column("expiresAt", DateTime(timezone=True), nullable=False)
    created_at = Column(
        "createdAt", DateTime(timezone=True), server_default=func.now(), nullable=False
    )

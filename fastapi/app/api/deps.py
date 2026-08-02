from __future__ import annotations

import logging
from urllib.parse import urlparse

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.critical_logging import log_critical_event
from app.core.database import SessionLocal
from app.core.security import decode_access_token, decode_refresh_token
from app.models.enums import Role
from app.models.user import User


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


security = HTTPBearer(auto_error=False)
_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _reject_cross_site_cookie_request(request: Request) -> None:
    """Apply an Origin check to unsafe requests authenticated by cookies.

    SameSite=Lax is the primary browser control.  The explicit check protects
    deployments where a browser accepts a permissive navigation or a proxy
    configuration changes.  Server-side Next requests commonly have no Origin
    header and are intentionally allowed.
    """
    if request.method.upper() not in _UNSAFE_METHODS:
        return
    origin = (request.headers.get("origin") or "").strip()
    if not origin:
        return
    expected = urlparse(settings.resolved_site_url())
    received = urlparse(origin)
    if (
        received.scheme.lower() != expected.scheme.lower()
        or received.netloc.lower() != expected.netloc.lower()
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid request origin.")


def _decode_request_credentials(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> tuple[dict | None, bool]:
    """Return payload and whether it came from an HttpOnly cookie."""
    if credentials:
        if credentials.scheme.lower() != "bearer":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
        try:
            return decode_access_token(credentials.credentials), False
        except Exception:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    access_cookie = request.cookies.get(settings.access_token_cookie_name)
    if access_cookie:
        try:
            return decode_access_token(access_cookie), True
        except Exception:
            # A refresh cookie may still establish the session after the short
            # access cookie expires.
            pass

    refresh_cookie = request.cookies.get(settings.refresh_token_cookie_name)
    if refresh_cookie:
        try:
            return decode_refresh_token(refresh_cookie), True
        except Exception:
            return None, True
    return None, False


def _user_from_payload(db: Session, payload: dict) -> User | None:
    user_id = payload.get("sub") or payload.get("user_id")
    email = payload.get("email")
    stmt = None
    if user_id:
        stmt = select(User).where(User.id == str(user_id))
    elif email:
        stmt = select(User).where(User.email == str(email))
    if stmt is None:
        return None

    user = db.execute(stmt).scalars().first()
    if not user:
        return None
    token_version = payload.get("ver")
    if not isinstance(token_version, int) or token_version != int(user.auth_version or 0):
        return None
    return user


def _resolve_optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
    db: Session,
) -> User | None:
    try:
        payload, used_cookie = _decode_request_credentials(request, credentials)
    except HTTPException:
        log_critical_event(
            domain="auth",
            event="invalid_access_token",
            message="Access token failed validation.",
            request=request,
            level=logging.WARNING,
        )
        raise
    if not payload:
        return None
    if used_cookie:
        _reject_cross_site_cookie_request(request)
    user = _user_from_payload(db, payload)
    if not user:
        log_critical_event(
            domain="auth",
            event="token_user_not_found_or_revoked",
            message="Authentication credential resolved to no active user session.",
            request=request,
            level=logging.WARNING,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return user


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    user = _resolve_optional_user(request, credentials, db)
    if user:
        return user
    log_critical_event(
        domain="auth",
        event="missing_authentication_credential",
        message="Protected endpoint called without a valid authentication credential.",
        request=request,
        level=logging.WARNING,
    )
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


def get_optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User | None:
    return _resolve_optional_user(request, credentials, db)


def require_admin(request: Request, user: User = Depends(get_current_user)) -> User:
    if user.role != Role.ADMIN:
        log_critical_event(
            domain="admin",
            event="unauthorized_admin_access",
            message="Non-admin user attempted to access admin endpoint.",
            request=request,
            context={"user_id": user.id},
            level=logging.WARNING,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
    return user

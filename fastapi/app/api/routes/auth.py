from __future__ import annotations

from datetime import datetime, timezone
import logging

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
import httpx
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.deps import _reject_cross_site_cookie_request, get_db
from app.core.config import settings
from app.core.critical_logging import log_critical_event
from app.core.rate_limit import SlidingWindowRateLimiter, enforce_rate_limit
from app.core.security import (
    GOOGLE_OAUTH_STATE_TTL_MINUTES,
    create_access_token,
    create_google_oauth_state_token,
    create_refresh_token,
    decode_refresh_token,
    generate_otp,
    validate_google_oauth_state_token,
    verify_otp,
)
from app.models.user import User
from app.models.verification_code import VerificationCode
from app.schemas.auth import GoogleCodeSignInIn, GoogleSignInIn, RequestCodeIn, VerifyCodeIn
from app.schemas.user import TokenOut, UserOut
from app.services.email import send_otp_email

router = APIRouter(prefix="/api/auth", tags=["auth"])
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_OAUTH_STATE_COOKIE_NAME = "aib_google_oauth_state"
GOOGLE_OAUTH_STATE_COOKIE_PATH = "/api/auth/google"
otp_request_limiter = SlidingWindowRateLimiter(limit=20, window_seconds=15 * 60)
otp_email_request_limiter = SlidingWindowRateLimiter(limit=5, window_seconds=15 * 60)
otp_verify_limiter = SlidingWindowRateLimiter(limit=20, window_seconds=15 * 60)
OTP_MAX_VERIFY_ATTEMPTS = 5


def _cookie_secure() -> bool:
    return settings.is_production()


def _cookie_max_age() -> int:
    return max(1, settings.refresh_token_expire_days * 24 * 60 * 60)


def _access_cookie_max_age() -> int:
    return max(1, settings.access_token_expire_minutes * 60)


def _set_access_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.access_token_cookie_name,
        value=token,
        httponly=True,
        secure=_cookie_secure(),
        samesite=settings.resolved_refresh_cookie_samesite(),
        path="/",
        max_age=_access_cookie_max_age(),
    )


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.refresh_token_cookie_name,
        value=token,
        httponly=True,
        secure=_cookie_secure(),
        samesite=settings.resolved_refresh_cookie_samesite(),
        path="/",
        max_age=_cookie_max_age(),
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.refresh_token_cookie_name,
        path="/",
        secure=_cookie_secure(),
        httponly=True,
        samesite=settings.resolved_refresh_cookie_samesite(),
    )


def _clear_access_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.access_token_cookie_name,
        path="/",
        secure=_cookie_secure(),
        httponly=True,
        samesite=settings.resolved_refresh_cookie_samesite(),
    )


def _set_google_oauth_state_cookie(response: Response, state: str) -> None:
    response.set_cookie(
        key=GOOGLE_OAUTH_STATE_COOKIE_NAME,
        value=state,
        httponly=True,
        secure=_cookie_secure(),
        # OAuth returns through a top-level navigation.  Keep this cookie
        # independent of the configurable session-cookie policy so it remains
        # a same-site CSRF binding even if sessions need a different setting.
        samesite="lax",
        path=GOOGLE_OAUTH_STATE_COOKIE_PATH,
        max_age=GOOGLE_OAUTH_STATE_TTL_MINUTES * 60,
    )


def _clear_google_oauth_state_cookie(response: Response) -> None:
    response.delete_cookie(
        key=GOOGLE_OAUTH_STATE_COOKIE_NAME,
        path=GOOGLE_OAUTH_STATE_COOKIE_PATH,
        secure=_cookie_secure(),
        httponly=True,
        samesite="lax",
    )


def _google_oauth_error_response(status_code: int, detail: str) -> JSONResponse:
    """Return an OAuth-code error while reliably consuming the state cookie.

    FastAPI does not carry headers set on an injected ``Response`` through an
    ``HTTPException``.  Build the error response directly so a failed token
    exchange cannot leave a valid state cookie available for another attempt.
    """
    response = JSONResponse(status_code=status_code, content={"detail": detail})
    _clear_google_oauth_state_cookie(response)
    return response


def _as_utc(value: datetime) -> datetime:
    """Normalize SQLite's naive timestamps while preserving production UTC values."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _build_auth_response(response: Response, user: User, db: Session) -> TokenOut:
    # Keep the account's authorization version stable when a new device signs
    # in or refreshes its session.  It is deliberately shared by all tokens
    # for the account, so rotating it here would sign out every other device.
    subject = {
        "sub": user.id,
        "email": user.email,
        "role": user.role.value,
        "name": user.name or "",
        "ver": user.auth_version,
    }
    token = create_access_token(
        subject
    )
    refresh_token = create_refresh_token(
        {"sub": user.id, "email": user.email, "ver": user.auth_version}
    )
    _set_access_cookie(response, token)
    _set_refresh_cookie(response, refresh_token)
    return TokenOut(user=UserOut.model_validate(user))


def _verify_google_id_token_or_401(raw_id_token: str, request: Request) -> dict:
    try:
        return id_token.verify_oauth2_token(
            raw_id_token,
            google_requests.Request(),
            settings.google_client_id,
        )
    except Exception:
        log_critical_event(
            domain="auth",
            event="google_token_validation_failed",
            message="Google ID token validation failed.",
            request=request,
            level=logging.WARNING,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.")


def _upsert_google_user_from_profile(
    profile: dict,
    request: Request,
    db: Session,
) -> User:
    email = str(profile.get("email") or "").lower().strip()
    if not email or profile.get("email_verified") is not True:
        log_critical_event(
            domain="auth",
            event="google_profile_missing_email",
            message="Google token did not include user email.",
            request=request,
            level=logging.WARNING,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.")

    user = db.execute(select(User).where(User.email == email)).scalars().first()
    if not user:
        user = User(email=email, name=profile.get("name"), image=profile.get("picture"))
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        if profile.get("name") and not user.name:
            user.name = profile.get("name")
        if profile.get("picture") and not user.image:
            user.image = profile.get("picture")
        db.commit()
    return user


@router.post("/request-code")
async def request_code(
    payload: RequestCodeIn,
    request: Request,
    db: Session = Depends(get_db),
):
    enforce_rate_limit(
        request,
        otp_request_limiter,
        detail="Too many verification-code requests. Please try again later.",
    )
    email = payload.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Please provide a valid email address.")
    if not otp_email_request_limiter.allow(email):
        log_critical_event(
            domain="auth",
            event="otp_email_rate_limit_reached",
            message="OTP request rate limit reached for an email address.",
            request=request,
            context={"email": email},
            level=logging.WARNING,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many verification-code requests. Please try again later.",
        )

    now = datetime.now(timezone.utc)
    last_code = (
        db.execute(
            select(VerificationCode)
            .where(VerificationCode.email == email)
            .order_by(VerificationCode.created_at.desc())
        )
        .scalars()
        .first()
    )
    if last_code and (now - _as_utc(last_code.created_at)).total_seconds() < 20:
        log_critical_event(
            domain="auth",
            event="otp_request_too_fast",
            message="OTP requested too frequently.",
            request=request,
            context={"email": email},
            level=logging.WARNING,
        )
        retry_after = max(1, int(20 - (now - _as_utc(last_code.created_at)).total_seconds()))
        return JSONResponse(
            status_code=429,
            content={
                "error": "Please wait a moment before requesting another code.",
                "retryAfterSec": retry_after,
            },
        )

    otp = generate_otp()
    db.execute(delete(VerificationCode).where(VerificationCode.email == email))
    db.add(
        VerificationCode(
            email=email,
            code_hash=otp["hash"],
            salt=otp["salt"],
            expires_at=otp["expires_at"],
        )
    )
    db.commit()

    try:
        await send_otp_email(email, str(otp["code"]))
    except Exception as exc:
        # The code should not remain valid if delivery failed.
        db.execute(delete(VerificationCode).where(VerificationCode.email == email))
        db.commit()
        log_critical_event(
            domain="auth",
            event="otp_delivery_failed",
            message="Failed to deliver OTP email.",
            request=request,
            context={"email": email},
            exc=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to send verification code. Please try again later.",
        )
    return {"ok": True}


@router.post("/verify-code", response_model=TokenOut, response_model_exclude_none=True)
def verify_code(
    payload: VerifyCodeIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    _reject_cross_site_cookie_request(request)
    enforce_rate_limit(
        request,
        otp_verify_limiter,
        detail="Too many verification attempts. Please request a new code later.",
    )
    email = payload.email.strip().lower()
    code = payload.code.strip()

    record = (
        db.execute(
            select(VerificationCode)
            .where(VerificationCode.email == email)
            .order_by(VerificationCode.created_at.desc())
            .with_for_update()
        )
        .scalars()
        .first()
    )
    if not record or _as_utc(record.expires_at) < datetime.now(timezone.utc):
        log_critical_event(
            domain="auth",
            event="otp_invalid_or_expired",
            message="OTP verification failed: invalid or expired code.",
            request=request,
            context={"email": email},
            level=logging.WARNING,
        )
        raise HTTPException(status_code=400, detail="Invalid or expired code.")
    if not verify_otp(code, record.salt, record.code_hash):
        record.attempt_count = int(record.attempt_count or 0) + 1
        attempts_exhausted = record.attempt_count >= OTP_MAX_VERIFY_ATTEMPTS
        if attempts_exhausted:
            db.delete(record)
        db.commit()
        log_critical_event(
            domain="auth",
            event="otp_verification_failed",
            message="OTP verification failed: hash mismatch.",
            request=request,
            context={
                "email": email,
                "attempts_exhausted": attempts_exhausted,
            },
            level=logging.WARNING,
        )
        raise HTTPException(status_code=400, detail="Invalid or expired code.")

    user = db.execute(select(User).where(User.email == email)).scalars().first()
    if not user:
        if not payload.name or not payload.name.strip():
            raise HTTPException(status_code=400, detail="Name is required.")
        user = User(email=email, name=payload.name.strip())
        db.add(user)
        db.commit()
        db.refresh(user)
    elif payload.name and not user.name:
        user.name = payload.name.strip()
        db.commit()
        db.refresh(user)

    db.execute(delete(VerificationCode).where(VerificationCode.email == email))
    db.commit()

    return _build_auth_response(response, user, db)


@router.post("/google", response_model=TokenOut, response_model_exclude_none=True)
def google_sign_in(
    payload: GoogleSignInIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    _reject_cross_site_cookie_request(request)
    if not settings.google_client_id:
        log_critical_event(
            domain="auth",
            event="google_auth_not_configured",
            message="Google sign-in requested but integration is not configured.",
            request=request,
        )
        raise HTTPException(status_code=400, detail="Google login is not configured.")

    info = _verify_google_id_token_or_401(payload.id_token, request)
    user = _upsert_google_user_from_profile(info, request, db)
    return _build_auth_response(response, user, db)


@router.post("/google/state")
def issue_google_oauth_state(request: Request, response: Response):
    """Bind an OAuth authorization-code flow to this browser before redirecting."""
    _reject_cross_site_cookie_request(request)
    state = create_google_oauth_state_token()
    _set_google_oauth_state_cookie(response, state)
    return {"state": state}


@router.post("/google/code", response_model=TokenOut, response_model_exclude_none=True)
def google_sign_in_with_code(
    payload: GoogleCodeSignInIn,
    request: Request,
    response: Response,
    oauth_state_cookie: str | None = Cookie(
        default=None, alias=GOOGLE_OAUTH_STATE_COOKIE_NAME
    ),
    db: Session = Depends(get_db),
):
    _reject_cross_site_cookie_request(request)
    state_is_valid = validate_google_oauth_state_token(
        received_state=payload.state,
        expected_state=oauth_state_cookie,
    )
    # Consume the state before exchanging the one-time code. This prevents a
    # callback URL from being replayed after a successful or failed exchange.
    _clear_google_oauth_state_cookie(response)
    if not state_is_valid:
        log_critical_event(
            domain="auth",
            event="google_oauth_state_invalid",
            message="Google authorization-code flow failed state validation.",
            request=request,
            level=logging.WARNING,
        )
        return _google_oauth_error_response(400, "Invalid Google sign-in state.")
    if not settings.google_client_id or not settings.google_client_secret:
        log_critical_event(
            domain="auth",
            event="google_auth_not_configured",
            message="Google code sign-in requested but integration is not configured.",
            request=request,
        )
        return _google_oauth_error_response(400, "Google login is not configured.")

    code = payload.code.strip()
    if not code:
        return _google_oauth_error_response(
            400, "Google authorization code is required."
        )
    redirect_uri = (payload.redirect_uri or "postmessage").strip() or "postmessage"
    allowed_redirect_uris = {
        "postmessage",
        f"{settings.resolved_site_url()}/auth/google/callback",
    }
    if redirect_uri not in allowed_redirect_uris:
        log_critical_event(
            domain="auth",
            event="google_redirect_uri_rejected",
            message="Google code exchange used an unapproved redirect URI.",
            request=request,
            level=logging.WARNING,
        )
        return _google_oauth_error_response(400, "Invalid Google redirect URI.")

    try:
        exchange_response = httpx.post(
            GOOGLE_TOKEN_ENDPOINT,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            headers={"Accept": "application/json"},
            timeout=10.0,
        )
    except Exception as exc:
        log_critical_event(
            domain="auth",
            event="google_code_exchange_request_failed",
            message="Google authorization code exchange request failed.",
            request=request,
            exc=exc,
        )
        return _google_oauth_error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Google sign-in is temporarily unavailable.",
        )

    try:
        exchange_payload = exchange_response.json()
    except ValueError:
        exchange_payload = {}

    if exchange_response.status_code >= 400:
        log_critical_event(
            domain="auth",
            event="google_code_exchange_failed",
            message="Google authorization code exchange failed.",
            request=request,
            context={
                "status_code": exchange_response.status_code,
                "error": exchange_payload.get("error"),
            },
            level=logging.WARNING,
        )
        return _google_oauth_error_response(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid Google authorization code.",
        )

    id_token_value = str(exchange_payload.get("id_token") or "").strip()
    if not id_token_value:
        log_critical_event(
            domain="auth",
            event="google_code_exchange_missing_id_token",
            message="Google token exchange did not return an ID token.",
            request=request,
            level=logging.WARNING,
        )
        return _google_oauth_error_response(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid Google authorization code.",
        )

    try:
        info = _verify_google_id_token_or_401(id_token_value, request)
        user = _upsert_google_user_from_profile(info, request, db)
    except HTTPException as exc:
        return _google_oauth_error_response(exc.status_code, str(exc.detail))
    return _build_auth_response(response, user, db)


@router.post("/refresh", response_model=TokenOut, response_model_exclude_none=True)
def refresh_access_token(
    request: Request,
    response: Response,
    refresh_cookie: str | None = Cookie(default=None, alias=settings.refresh_token_cookie_name),
    db: Session = Depends(get_db),
):
    _reject_cross_site_cookie_request(request)
    if not refresh_cookie:
        log_critical_event(
            domain="auth",
            event="refresh_cookie_missing",
            message="Refresh token cookie is missing.",
            request=request,
            level=logging.WARNING,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    try:
        payload = decode_refresh_token(refresh_cookie)
    except Exception:
        log_critical_event(
            domain="auth",
            event="refresh_token_invalid",
            message="Refresh token failed validation.",
            request=request,
            level=logging.WARNING,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    user_id = payload.get("sub")
    email = payload.get("email")
    stmt = None
    if user_id:
        stmt = select(User).where(User.id == str(user_id))
    elif email:
        stmt = select(User).where(User.email == str(email))
    if stmt is None:
        log_critical_event(
            domain="auth",
            event="refresh_token_without_identity",
            message="Refresh token payload does not include user identity.",
            request=request,
            level=logging.WARNING,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    user = db.execute(stmt).scalars().first()
    if not user:
        log_critical_event(
            domain="auth",
            event="refresh_user_not_found",
            message="Refresh token resolved to unknown user.",
            request=request,
            level=logging.WARNING,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    if payload.get("ver") != user.auth_version:
        log_critical_event(
            domain="auth",
            event="refresh_token_revoked",
            message="Refresh token session version is no longer active.",
            request=request,
            level=logging.WARNING,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    return _build_auth_response(response, user, db)


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    refresh_cookie: str | None = Cookie(default=None, alias=settings.refresh_token_cookie_name),
):
    _reject_cross_site_cookie_request(request)
    # Cookies belong to this browser/device.  Clearing them locally must not
    # revoke valid sessions on the customer's other devices.
    _clear_access_cookie(response)
    _clear_refresh_cookie(response)
    return {"ok": True}

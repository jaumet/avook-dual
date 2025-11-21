from datetime import datetime, timedelta, timezone
from typing import Literal, Optional
from urllib.parse import urlencode, urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..email_utils import send_magic_link_email
from ..models import MagicLinkToken, User
from ..schemas import (
    GenericDetailResponse,
    MagicLinkRequest,
    MagicLoginResponse,
    UserRead,
)
from ..security import create_access_token, generate_magic_raw_token, hash_token
from ..settings import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

_GENERIC_RESPONSE = GenericDetailResponse(
    detail="If this email is registered, a login link has been sent."
)


@router.post("/magic-link/request", response_model=GenericDetailResponse)
def request_magic_link(
    payload: MagicLinkRequest, request: Request, db: Session = Depends(get_db)
) -> GenericDetailResponse:
    email_norm = payload.email.strip().lower()

    user = (
        db.query(User)
        .filter(
            User.email == email_norm,
            User.is_active.is_(True),
        )
        .first()
    )

    if not user or not user.has_any_package():
        return _GENERIC_RESPONSE

    _enforce_rate_limit(db, user)

    raw_token = generate_magic_raw_token()
    token_hash = hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.magic_link_expiration_minutes
    )

    magic_link_token = MagicLinkToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
        created_ip=request.client.host if request.client else None,
        created_user_agent=request.headers.get("user-agent"),
    )
    db.add(magic_link_token)
    db.commit()

    magic_link_url = _build_magic_link_url(raw_token)
    send_magic_link_email(user.email, magic_link_url, raw_token)

    return _GENERIC_RESPONSE


@router.get(
    "/magic-login",
    response_model=MagicLoginResponse,
    responses={307: {"description": "Redirect with HttpOnly cookie"}},
)
def magic_login(
    token: str = Query(..., description="Raw magic link token"),
    request: Request = None,
    response_mode: Literal["json", "cookie"] = Query(
        "json", description="Choose between JSON response or HttpOnly cookie + redirect."
    ),
    redirect_to: Optional[str] = Query(
        None,
        description="Override redirect target when using response_mode=cookie.",
    ),
    db: Session = Depends(get_db),
) -> MagicLoginResponse:
    token_hash = hash_token(token)
    now = datetime.now(timezone.utc)

    magic_link_token = (
        db.query(MagicLinkToken).filter(MagicLinkToken.token_hash == token_hash).first()
    )

    if not magic_link_token:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    if magic_link_token.used_at is not None:
        raise HTTPException(status_code=400, detail="Token already used")

    expires_at = _ensure_utc(magic_link_token.expires_at)
    if expires_at < now:
        raise HTTPException(status_code=400, detail="Token expired")

    user = (
        db.query(User)
        .filter(User.id == magic_link_token.user_id, User.is_active.is_(True))
        .first()
    )

    if not user:
        raise HTTPException(status_code=403, detail="User not allowed")

    current_ip, current_ua = _extract_request_fingerprint(request)
    ip_differs = bool(
        magic_link_token.created_ip and current_ip and current_ip != magic_link_token.created_ip
    )
    ua_differs = bool(
        magic_link_token.created_user_agent
        and current_ua
        and current_ua != magic_link_token.created_user_agent
    )

    if settings.enforce_magic_link_ip_match and ip_differs:
        raise HTTPException(status_code=400, detail="Suspicious login attempt")

    if settings.block_suspicious_login_attempts and ip_differs and ua_differs:
        raise HTTPException(status_code=400, detail="Suspicious login attempt")

    magic_link_token.used_at = now
    db.add(magic_link_token)
    db.commit()

    access_token = create_access_token({"sub": str(user.id)})

    if response_mode == "cookie":
        return _build_cookie_response(access_token, redirect_to, request)

    return MagicLoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=user,
    )


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.post("/logout", response_model=GenericDetailResponse)
def logout(request: Request) -> JSONResponse:
    response = JSONResponse({"detail": "Sessió tancada"})
    response.delete_cookie(
        key=settings.auth_cookie_name,
        **_cookie_kwargs(request),
    )
    return response


def _enforce_rate_limit(db: Session, user: User) -> None:
    window_start = datetime.now(timezone.utc) - timedelta(
        minutes=settings.magic_link_rate_limit_window_minutes
    )
    recent_attempts = (
        db.query(MagicLinkToken)
        .filter(
            MagicLinkToken.user_id == user.id,
            MagicLinkToken.created_at >= window_start,
        )
        .count()
    )
    if recent_attempts >= settings.magic_link_rate_limit_max_requests:
        raise HTTPException(
            status_code=429,
            detail="Too many magic link requests. Please try again later.",
        )


def _extract_request_fingerprint(request: Optional[Request]) -> tuple[Optional[str], Optional[str]]:
    if not request:
        return None, None
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return ip, user_agent


def _build_cookie_response(
    access_token: str, redirect_to: Optional[str], request: Optional[Request] = None
):
    target = redirect_to or settings.post_login_redirect_url
    if not target:
        raise HTTPException(status_code=400, detail="Missing redirect target")
    if not _redirect_allowed(target):
        raise HTTPException(status_code=400, detail="Redirect host not allowed")

    response = RedirectResponse(url=target, status_code=307)
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=access_token,
        max_age=settings.jwt_expiration_minutes * 60,
        **_cookie_kwargs(request),
    )
    return response


def _cookie_kwargs(request: Optional[Request] = None) -> dict:
    base = dict(
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
    )
    if request and request.url.scheme == "http":
        base["secure"] = False
    if settings.auth_cookie_domain:
        base["domain"] = settings.auth_cookie_domain
    return base


def _redirect_allowed(url: str) -> bool:
    parsed = urlparse(url)
    if not parsed.netloc:
        return True  # relative URLs
    hostname = parsed.hostname
    if not hostname:
        return False
    return hostname in settings.allowed_redirect_hosts


def _build_magic_link_url(raw_token: str) -> str:
    """Attach token (and redirect override, when configured) to the frontend URL."""
    query = {"token": raw_token}
    if settings.post_login_redirect_url:
        query["redirect"] = settings.post_login_redirect_url
    separator = "&" if "?" in settings.frontend_magic_login_url else "?"
    return f"{settings.frontend_magic_login_url}{separator}{urlencode(query)}"


def _ensure_utc(value: datetime) -> datetime:
    """Normalize DB datetimes (which may be naive under SQLite) to UTC."""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)

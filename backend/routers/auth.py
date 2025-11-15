from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..email_utils import send_magic_link_email
from ..models import MagicLinkToken, User
from ..schemas import GenericDetailResponse, MagicLinkRequest, MagicLoginResponse
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
            User.full_access.is_(True),
        )
        .first()
    )

    if not user:
        return _GENERIC_RESPONSE

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

    magic_link_url = f"{settings.frontend_magic_login_url}?token={raw_token}"
    send_magic_link_email(user.email, magic_link_url)

    return _GENERIC_RESPONSE


@router.get("/magic-login", response_model=MagicLoginResponse)
def magic_login(
    token: str = Query(..., description="Raw magic link token"),
    request: Request = None,
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

    if magic_link_token.expires_at < now:
        raise HTTPException(status_code=400, detail="Token expired")

    user = (
        db.query(User)
        .filter(User.id == magic_link_token.user_id, User.is_active.is_(True))
        .first()
    )

    if not user or not user.full_access:
        raise HTTPException(status_code=403, detail="User not allowed")

    if (
        settings.enforce_magic_link_ip_match
        and magic_link_token.created_ip
        and request
        and request.client
    ):
        current_ip = request.client.host
        if current_ip and current_ip != magic_link_token.created_ip:
            raise HTTPException(status_code=400, detail="Suspicious login attempt")

    magic_link_token.used_at = now
    db.add(magic_link_token)
    db.commit()

    access_token = create_access_token({"sub": str(user.id)})

    return MagicLoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=user,
    )

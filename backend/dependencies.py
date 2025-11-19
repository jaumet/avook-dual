from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from .database import get_db
from .models import User
from .settings import get_settings


settings = get_settings()
oauth2_scheme = HTTPBearer(auto_error=False)


def _extract_token(
    request: Request, credentials: Optional[HTTPAuthorizationCredentials]
) -> Optional[str]:
    if credentials and credentials.credentials:
        return credentials.credentials
    return request.cookies.get(settings.auth_cookie_name)


def _decode_token(token: str) -> int:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except JWTError as exc:  # pragma: no cover - runtime validation
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    try:
        return int(user_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload") from exc


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    token = _extract_token(request, credentials)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user_id = _decode_token(token)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    return user


def get_current_full_access_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.has_any_package():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Subscription required")
    return current_user

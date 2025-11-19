from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class MagicLinkRequest(BaseModel):
    email: EmailStr


class GenericDetailResponse(BaseModel):
    detail: str


class UserRead(BaseModel):
    id: int
    email: EmailStr
    full_access: bool
    packages: list[str] = []

    class Config:
        orm_mode = True


class MagicLoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserRead


class MagicLinkTokenRead(BaseModel):
    id: str
    user_id: int
    created_at: datetime
    expires_at: datetime
    used_at: Optional[datetime]

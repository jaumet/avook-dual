from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .database import Base


def _utcnow() -> datetime:
    """Return a timezone-aware UTC timestamp for SQLite/Postgres parity."""

    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    full_access = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    magic_link_tokens = relationship(
        "MagicLinkToken", back_populates="user", cascade="all, delete-orphan"
    )
    package_links = relationship(
        "UserPackage", back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def packages(self) -> list[str]:  # pragma: no cover - convenience proxy
        if self.full_access:
            try:
                from .catalog import CatalogConfigError, get_packages

                return [pkg.get("id") for pkg in get_packages() if pkg.get("id")]
            except CatalogConfigError:
                pass
        return [link.package_id for link in self.package_links]

    def has_any_package(self) -> bool:
        return self.full_access or bool(self.package_links)

    def can_access_package(self, package_id: str) -> bool:
        return self.full_access or package_id in self.packages


class MagicLinkToken(Base):
    __tablename__ = "magic_link_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_ip = Column(String, nullable=True)
    created_user_agent = Column(Text, nullable=True)

    user = relationship("User", back_populates="magic_link_tokens")


class UserPackage(Base):
    __tablename__ = "user_packages"

    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    package_id = Column(String, primary_key=True)
    granted_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    user = relationship("User", back_populates="package_links")

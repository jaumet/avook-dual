from functools import lru_cache
from typing import Optional

from pydantic import AnyUrl, BaseSettings, Field


class Settings(BaseSettings):
    database_url: AnyUrl = Field(
        "sqlite:///./audiovook.db",
        description="SQLAlchemy database URL. Defaults to local SQLite for development.",
    )
    jwt_secret_key: str = Field(..., description="Secret key used to sign JWT access tokens.")
    jwt_algorithm: str = Field("HS256", description="JWT signing algorithm.")
    jwt_expiration_minutes: int = Field(
        60 * 24, description="Number of minutes a standard access token remains valid."
    )
    magic_link_expiration_minutes: int = Field(
        15, description="Magic link validity period in minutes."
    )
    frontend_magic_login_url: AnyUrl = Field(
        "https://audiovook.com/auth/magic-login",
        description="Base URL where users land when clicking on a magic link.",
    )
    stripe_webhook_secret: Optional[str] = Field(
        None, description="Stripe webhook signing secret used to validate events."
    )
    email_from_address: str = Field(
        "no-reply@audiovook.com", description="Sender email used for transactional emails."
    )
    smtp_host: Optional[str] = Field(None, description="SMTP host for sending transactional email.")
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_port: int = 587
    smtp_use_tls: bool = True
    enforce_magic_link_ip_match: bool = Field(
        False,
        description="If true, the backend will reject magic link consumption when the IP does not match the original request.",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()

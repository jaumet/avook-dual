import json
from functools import lru_cache
from typing import List, Optional

from pydantic import AnyUrl, BaseSettings, Field


DEFAULT_ALLOWED_REDIRECT_HOSTS = ["audiovook.com", "localhost", "127.0.0.1"]
DEFAULT_ALLOWED_CORS_ORIGINS = [
    "https://audiovook.com",
    "https://audiovook.com/dual",
    "https://audiovook.com/dual/",
    "http://localhost:6060",
    "http://127.0.0.1:6060",
]


class Settings(BaseSettings):
    database_url: str = Field(
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
    magic_link_rate_limit_window_minutes: int = Field(
        60, description="Window (in minutes) used to evaluate per-email rate limits."
    )
    magic_link_rate_limit_max_requests: int = Field(
        5, description="Maximum number of magic links a user can request within the configured window."
    )
    frontend_magic_login_url: AnyUrl = Field(
        "https://dual.local/auth/magic-login",
        description="Base URL where users land when clicking on a magic link.",
    )
    post_login_redirect_url: Optional[AnyUrl] = Field(
        "https://dual.local/?login=ok",
        description="Default URL used when issuing HttpOnly cookie responses after magic login.",
    )
    stripe_webhook_secret: Optional[str] = Field(
        None, description="Stripe webhook signing secret used to validate events."
    )
    stripe_secret_key: Optional[str] = Field(
        None, description="Stripe secret key used to fetch checkout line items."
    )
    email_from_address: str = Field(
        "no-reply@audiovook.com", description="Sender email used for transactional emails."
    )
    email_enabled: bool = Field(
        True,
        description="Global toggle to disable outbound email (useful for local development).",
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
    block_suspicious_login_attempts: bool = Field(
        True,
        description="If true, reject magic links when both the IP address and user-agent change between request and login.",
    )
    auth_cookie_name: str = Field(
        "audiovook_access_token",
        description="Name of the HttpOnly cookie that stores JWTs when using cookie response mode.",
    )
    auth_cookie_secure: bool = Field(
        True, description="Whether the authentication cookie should be marked as secure."
    )
    auth_cookie_domain: Optional[str] = Field(
        None, description="Optional domain attribute applied to the authentication cookie."
    )
    auth_cookie_samesite: str = Field(
        "lax", description="SameSite mode for the authentication cookie (lax/strict/none)."
    )
    allowed_redirect_hosts: List[str] = Field(
        default_factory=lambda: DEFAULT_ALLOWED_REDIRECT_HOSTS.copy(),
        description="List of hostnames that are allowed as redirect targets when issuing HttpOnly cookie responses.",
    )
    allowed_cors_origins: List[str] = Field(
        default_factory=lambda: DEFAULT_ALLOWED_CORS_ORIGINS.copy(),
        description="Origins that may call the API with credentials for catalog and auth requests.",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

        @staticmethod
        def _parse_list(raw_value: Optional[str], default: List[str]) -> List[str]:
            if raw_value is None:
                return default.copy()

            raw = raw_value.strip()
            if not raw:
                return default.copy()

            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        return parsed
                except json.JSONDecodeError:
                    pass

            parsed = [item.strip() for item in raw.split(",") if item.strip()]
            return parsed or default.copy()

        @classmethod
        def parse_env_var(cls, field_name: str, raw_value: str):
            if field_name == "allowed_redirect_hosts":
                return cls._parse_list(raw_value, DEFAULT_ALLOWED_REDIRECT_HOSTS)
            if field_name == "allowed_cors_origins":
                return cls._parse_list(raw_value, DEFAULT_ALLOWED_CORS_ORIGINS)
            return super().parse_env_var(field_name, raw_value)


@lru_cache
def get_settings() -> Settings:
    return Settings()

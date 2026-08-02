from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from urllib.parse import urlparse


_LOCAL_ENVIRONMENTS = {"development", "dev", "local", "test"}
_PRODUCTION_ENVIRONMENTS = {"production", "prod"}
_INSECURE_AUTH_SECRETS = {
    "",
    "dev-insecure-auth-secret-change-me",
    "replace-with-a-long-random-string",
    "your-auth-secret",
    "changeme",
    "change-me",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    # Do not default to development: a missing deployment variable must fail
    # closed during application startup instead of enabling known dev secrets
    # and non-Secure cookies on a public host.
    environment: str = Field(default="", alias="ENVIRONMENT")
    database_url: str = Field(default="", alias="DATABASE_URL")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    betterstack_source_token: str | None = Field(default=None, alias="BETTERSTACK_SOURCE_TOKEN")
    betterstack_ingest_url: str = Field(
        default="https://in.logs.betterstack.com",
        alias="BETTERSTACK_INGEST_URL",
    )

    auth_secret: str = Field(default="", alias="AUTH_SECRET")
    # Access credentials are deliberately short-lived.  The longer session is
    # held only in an HttpOnly refresh cookie.
    access_token_expire_minutes: int = Field(default=15)
    access_token_cookie_name: str = Field(default="aib_access", alias="ACCESS_TOKEN_COOKIE_NAME")
    refresh_token_expire_days: int = Field(default=30, alias="REFRESH_TOKEN_EXPIRE_DAYS")
    refresh_token_cookie_name: str = Field(default="aib_refresh", alias="REFRESH_TOKEN_COOKIE_NAME")
    refresh_token_cookie_samesite: str = Field(default="lax", alias="REFRESH_TOKEN_COOKIE_SAMESITE")

    admin_email: str = Field(default="allinbloom.us@gmail.com", alias="ADMIN_EMAIL")
    resend_api_key: str | None = Field(default=None, alias="RESEND_API_KEY")
    email_from: str = Field(
        default="All in Bloom Floral Studio <allinbloom.us@gmail.com>",
        alias="EMAIL_FROM",
    )
    email_reply_to: str = Field(
        default="allinbloom.us@gmail.com",
        alias="EMAIL_REPLY_TO",
    )

    google_client_id: str | None = Field(default=None, alias="GOOGLE_CLIENT_ID")
    google_client_secret: str | None = Field(
        default=None, alias="GOOGLE_CLIENT_SECRET"
    )

    stripe_secret_key: str | None = Field(default=None, alias="STRIPE_SECRET_KEY")
    stripe_webhook_secret: str | None = Field(
        default=None, alias="STRIPE_WEBHOOK_SECRET"
    )
    paypal_client_id: str | None = Field(default=None, alias="PAYPAL_CLIENT_ID")
    paypal_client_secret: str | None = Field(default=None, alias="PAYPAL_CLIENT_SECRET")
    paypal_webhook_id: str | None = Field(default=None, alias="PAYPAL_WEBHOOK_ID")
    paypal_env: str = Field(default="sandbox", alias="PAYPAL_ENV")

    site_url: str = Field(default="http://localhost:3000", alias="SITE_URL")

    google_maps_api_key: str | None = Field(
        default=None, alias="GOOGLE_MAPS_API_KEY"
    )
    trust_proxy_headers: bool = Field(default=False, alias="TRUST_PROXY_HEADERS")
    delivery_base_address: str = Field(
        default="1995 Hicks Rd, Rolling Meadows, IL 60008, USA",
        alias="DELIVERY_BASE_ADDRESS",
    )

    cloudinary_cloud_name: str | None = Field(
        default=None, alias="CLOUDINARY_CLOUD_NAME"
    )
    cloudinary_upload_preset: str | None = Field(
        default=None, alias="CLOUDINARY_UPLOAD_PRESET"
    )

    def normalized_database_url(self) -> str:
        value = self.database_url.strip()
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    def resolved_auth_secret(self) -> str:
        return (self.auth_secret or "").strip()

    def environment_name(self) -> str:
        return (self.environment or "").strip().lower()

    def is_development(self) -> bool:
        return self.environment_name() in _LOCAL_ENVIRONMENTS

    def is_production(self) -> bool:
        return self.environment_name() in _PRODUCTION_ENVIRONMENTS

    def validate_runtime_configuration(self) -> None:
        environment = self.environment_name()
        if environment not in _LOCAL_ENVIRONMENTS | _PRODUCTION_ENVIRONMENTS:
            raise RuntimeError(
                "ENVIRONMENT must be explicitly set to development, test, local, or production."
            )

        secret = self.resolved_auth_secret()
        if not self._is_safe_auth_secret(secret):
            raise RuntimeError(
                "AUTH_SECRET must be a unique, non-placeholder value with at least 32 characters."
            )

        parsed_site_url = urlparse(self.resolved_site_url())
        if parsed_site_url.scheme not in {"http", "https"} or not parsed_site_url.netloc:
            raise RuntimeError("SITE_URL must be an absolute http(s) URL.")
        if self.is_production() and parsed_site_url.scheme != "https":
            raise RuntimeError("SITE_URL must use HTTPS in production.")

    @staticmethod
    def _is_safe_auth_secret(value: str) -> bool:
        normalized = (value or "").strip()
        if len(normalized) < 32 or normalized.lower() in _INSECURE_AUTH_SECRETS:
            return False
        # This is not a substitute for a password manager/generated secret,
        # but rejects trivially repeated low-entropy values while accepting
        # standard 32-byte hex and URL-safe random strings.
        return len(set(normalized)) >= 12

    def resolved_refresh_cookie_samesite(self) -> str:
        value = (self.refresh_token_cookie_samesite or "lax").strip().lower()
        if value in {"lax", "strict", "none"}:
            return value
        return "lax"

    def resolved_site_url(self) -> str:
        value = self.site_url
        return (value or "http://localhost:3000").rstrip("/")


settings = Settings()

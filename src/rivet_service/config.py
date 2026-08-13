"""All service-layer environment configuration in one place (Phase 6,
docs/saas-buildout.md section 3). Nothing outside this module reads
``os.environ`` directly -- new settings get a field here, not an ad hoc
``os.getenv`` call somewhere else.

REDIS_URL and object storage credentials still don't exist yet (Phase 8);
billing keys are Phase 10. Auth-related settings were added in Phase 7.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "rivet-service"
    env: str = "development"
    database_url: str = "postgresql+psycopg://rivet:rivet@localhost:5432/rivet"

    # Phase 7 (auth). secret_key signs email-verification/password-reset
    # tokens (auth/tokens.py) -- session tokens themselves are opaque
    # random values looked up against a hash in the sessions table, not
    # signed, so a leaked secret_key can't forge a live session, only a
    # verify/reset link (which still requires the target account to exist
    # and expires quickly). The default below is dev-only and must be
    # overridden via SECRET_KEY in any real deployment.
    secret_key: str = "dev-only-insecure-secret-key-override-me"
    session_ttl_days: int = 30
    email_verification_token_ttl_hours: int = 24
    password_reset_token_ttl_hours: int = 2
    # Controls the session cookie's Secure flag -- browsers refuse to send
    # `Secure` cookies over plain http://, so local dev needs it off.
    cookie_secure: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()

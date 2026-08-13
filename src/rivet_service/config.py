"""All service-layer environment configuration in one place (Phase 6,
docs/saas-buildout.md section 3). Nothing outside this module reads
``os.environ`` directly -- new settings get a field here, not an ad hoc
``os.getenv`` call somewhere else.

Auth settings were added in Phase 7; jobs/storage settings in Phase 8;
billing settings in Phase 10; hardening settings in Phase 11.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

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

    # Phase 8 (jobs).
    redis_url: str = "redis://localhost:6379/0"
    # "A pathological request must die, not pin a worker" (section 6) --
    # generously above real generation time (well under a second) so it
    # only ever fires on something actually stuck.
    job_timeout_seconds: int = 120

    # Phase 8 (storage). "local" needs no cloud account for `docker
    # compose up` (section 6); "s3" works against real AWS S3 (the
    # decided deploy target) or MinIO by setting s3_endpoint_url.
    storage_backend: Literal["local", "s3"] = "local"
    storage_local_dir: str = "./storage_data"
    # Used to build signed download URLs for the local backend, which has
    # no presigned-URL concept of its own -- see storage/local.py.
    storage_public_base_url: str = "http://localhost:8000"
    # "Presigned URLs expire in minutes, not hours" (section 11).
    artifact_url_ttl_seconds: int = 300

    s3_bucket: str = "rivet-artifacts"
    s3_endpoint_url: str | None = None  # set for MinIO; unset means real AWS
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_region: str = "us-east-1"

    # Phase 10 (billing). None by default -- billing routes raise a clear
    # 503 rather than a confusing Stripe SDK error if these are unset
    # (see api/v1/billing.py), so `docker compose up` doesn't need a real
    # Stripe account for the rest of the service to work.
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    # No stripe_price_id_* settings here -- Plan.provider_price_id (the
    # `plans` table) is the one place a plan code maps to a Stripe price,
    # same reasoning as billing/entitlements.py: "limits live here, not
    # scattered through if plan == 'pro' branches." An operator sets it
    # per-plan (a real Stripe Price id) once a real Stripe account exists;
    # NULL until then, and the checkout route raises a clear 503 for a
    # plan that isn't priced yet rather than silently using the wrong id.

    # Where Stripe redirects the browser after Checkout/the Customer
    # Portal -- the frontend's own routes, not this API's.
    billing_checkout_success_url: str = "http://localhost:3000/billing/success"
    billing_checkout_cancel_url: str = "http://localhost:3000/billing/cancel"
    billing_portal_return_url: str = "http://localhost:3000/billing"

    # Phase 11 (hardening).

    # Comma-separated, not JSON -- an operator setting an env var by hand
    # shouldn't need to think about shell-quoting a JSON array. No
    # frontend is deployed anywhere yet (built separately, per section 9);
    # this default is a local dev server's origin, not a production one.
    cors_allowed_origins: str = "http://localhost:3000"

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    # None by default, same as the Stripe keys -- sentry_sdk.init() is
    # skipped entirely in main.py when unset, so no real Sentry project
    # is required for the rest of the service to work.
    sentry_dsn: str | None = None

    # Fixed-window counters in Redis (rate_limit.py). Deliberately simple
    # (INCR + EXPIRE, not a sliding window or token bucket) -- easy to
    # reason about and debug, which matters more here than smoothing
    # burst traffic at the edges of a window. Defaults are a starting
    # point, not a researched number; tune once real traffic exists.
    rate_limit_window_seconds: int = 60
    rate_limit_unauthenticated_max: int = 30  # per IP
    rate_limit_authenticated_max: int = 120  # per org

    # Stored on every user at registration (auth/register requires
    # accept_tos=true). "unreleased-draft" until a lawyer-reviewed ToS
    # and Privacy Policy exist -- see docs/saas-buildout.md section 12.
    # Bump this string (and re-prompt existing users to re-accept, not
    # built yet) the day a real version ships.
    tos_version: str = "unreleased-draft"


@lru_cache
def get_settings() -> Settings:
    return Settings()

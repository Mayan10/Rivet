"""All service-layer environment configuration in one place (Phase 6,
docs/saas-buildout.md section 3). Nothing outside this module reads
``os.environ`` directly -- new settings get a field here, not an ad hoc
``os.getenv`` call somewhere else.

Deliberately minimal for Phase 6 ("FastAPI skeleton... nothing else"):
just enough to stand up the app and connect to Postgres. REDIS_URL,
object storage credentials, auth secrets, and billing keys get added in
the phases that actually use them (8, 8, 7, 10 respectively) rather than
declared speculatively now.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "rivet-service"
    env: str = "development"
    database_url: str = "postgresql+psycopg://rivet:rivet@localhost:5432/rivet"


@lru_cache
def get_settings() -> Settings:
    return Settings()

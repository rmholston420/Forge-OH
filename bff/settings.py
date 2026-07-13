"""
bff/settings.py

Centralised runtime configuration via Pydantic Settings.
All environment-variable defaults are the canonical single source of truth
for port numbers and external service URLs.

Port assignments (project canonical):
  BFF  → 8081
  OpenHands SDK  → 8090
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # -----------------------------------------------------------------------
    # BFF server
    # -----------------------------------------------------------------------
    bff_host: str = "0.0.0.0"
    bff_port: int = 8081

    # -----------------------------------------------------------------------
    # OpenHands SDK (agent runtime)
    # Port 8090 is the canonical SDK port for this project.
    # -----------------------------------------------------------------------
    openhands_base_url: str = "http://localhost:8090"
    openhands_api_key: str = ""

    # -----------------------------------------------------------------------
    # Auth
    # -----------------------------------------------------------------------
    secret_key: str = "change-me-in-production"
    token_ttl_hours: int = 8

    # -----------------------------------------------------------------------
    # Feature flags
    # -----------------------------------------------------------------------
    feature_rigpa_lms_enabled: bool = False

    # -----------------------------------------------------------------------
    # Observability
    # -----------------------------------------------------------------------
    otel_exporter_otlp_endpoint: str = ""
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

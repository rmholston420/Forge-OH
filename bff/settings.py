"""
bff/settings.py

Centralised runtime configuration via Pydantic Settings.
All environment-variable defaults are the canonical single source of truth
for port numbers and external service URLs.

Port assignments (project canonical):
  BFF -> 8081
  OpenHands SDK -> 8090
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Slice D: also read Neo4j creds from a separate gitignored file so the
    # sensitive password never lands in the shared .env. Files are read in
    # order; later files override earlier ones for any duplicate keys.
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.neo4j"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # BFF server
    bff_host: str = "0.0.0.0"
    bff_port: int = 8081

    # OpenHands SDK (agent runtime)
    openhands_base_url: str = "http://localhost:8090"
    openhands_api_key: str = ""

    # Compatibility with existing env vars in your shell/.env
    openhands_sdk_version: str | None = None
    openhands_agent_server_host: str | None = None
    openhands_agent_server_port: int | None = None
    openhands_agent_server_base_url: str | None = None
    openhands_persist_dir: str | None = None
    oh_secret_key: str | None = None

    # Observability
    otel_exporter_otlp_endpoint: str = ""
    log_level: str = "INFO"

    # Slice D — RepoGraph / Neo4j (DozerDB on Colossus)
    # Populated from ~/dev/forge-oh/.env.neo4j on Colossus. Password is never
    # committed. Empty defaults let unit tests run without a live Neo4j.
    neo4j_bolt_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    neo4j_database: str = "forgeoh"
    # If false, /api/repograph/* endpoints return 503 without contacting Neo4j.
    # Set to true only after Colossus verifies the DB is reachable.
    repograph_enabled: bool = False

    # Stage 4.4 — Serena LSPClient (MCP passthrough).
    # When true, BFF startup calls `POST /api/mcp` to register a Serena MCP
    # server if one is not already registered upstream. See ADR-018 for the
    # locked launch-verb + no-language-gate rationale.
    serena_enabled: bool = False
    # Workspace path Serena is asked to index at registration time. Serena's
    # stdio server takes a single `--project` at launch; per-tool retargeting
    # is out of scope for Stage 4.4.
    serena_workspace_default: str = "/home/rmholston/dev/forge-oh"
    # Pinned to Serena upstream HEAD as of 2026-08-06 00:48 EDT so `uvx`
    # resolves to a reproducible commit. Update in a follow-up commit paired
    # with a PORTING_LEDGER bump.
    serena_pin_sha: str = "c7af2c09ef45faa4367c0e2a9f770fb73a62a612"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

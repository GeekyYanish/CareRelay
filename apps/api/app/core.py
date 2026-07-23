from __future__ import annotations

import json
import logging
import re
import sys
from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(url: str) -> str:
    """Map provider URLs to SQLAlchemy + psycopg v3 (Render/Neon default to bare postgresql://)."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "CareRelay"
    agent_provider: str = "gemini"
    orchestrator_provider: str = "lyzr"
    retrieval_provider: str = "qdrant"
    mcp_provider: str = "google-cloud"
    a2a_enabled: bool = True
    database_url: str = "sqlite:///./carerelay.db"
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"
    jwt_secret: str = ""
    a2a_shared_token: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-latest"
    lyzr_api_key: str = ""
    lyzr_workflow_id: str = ""
    lyzr_api_base: str = "https://inference.studio.lyzr.ai/api"
    lyzr_timeout_seconds: float = 45.0
    lyzr_poll_interval_seconds: float = 0.5
    require_live_orchestration: bool = False
    allow_local_origins: bool = False
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://127.0.0.1:5174"
    public_api_base_url: str = "http://localhost:8000"
    google_cloud_project: str = ""
    google_cloud_mcp_token: str = ""
    clinical_rules_path: str = "../../../packages/clinical-rules/clinical_v1.yaml"
    demo_data_path: str = "../../../packages/demo-data/scenarios.json"
    retrieval_threshold: float = 0.70
    low_risk_uncertainty_max: float = 0.25
    provider_timeout_seconds: float = 2.0
    provision_demo_users: bool = False
    enable_demo_scenarios: bool = True

    @field_validator("database_url", mode="before")
    @classmethod
    def use_psycopg_driver(cls, value: object) -> object:
        if isinstance(value, str):
            return normalize_database_url(value)
        return value

    @model_validator(mode="after")
    def reject_unsafe_production_configuration(self) -> "Settings":
        errors: list[str] = []
        if self.database_url.startswith("sqlite"):
            errors.append("DATABASE_URL must use PostgreSQL")
        if len(self.jwt_secret) < 32:
            errors.append("JWT_SECRET must contain at least 32 characters")
        if self.a2a_enabled and len(self.a2a_shared_token) < 32:
            errors.append("A2A_SHARED_TOKEN must contain at least 32 characters")
        # Live path: Lyzr required. Demo/local path: deterministic agents are allowed so
        # Routine / Self-Care remain reachable when SuperFlow times out or is misconfigured.
        if self.require_live_orchestration:
            if self.orchestrator_provider.lower() != "lyzr":
                errors.append("ORCHESTRATOR_PROVIDER must be lyzr when REQUIRE_LIVE_ORCHESTRATION=true")
            if not self.lyzr_api_key or not self.lyzr_workflow_id:
                errors.append("LYZR_API_KEY and LYZR_WORKFLOW_ID are required when REQUIRE_LIVE_ORCHESTRATION=true")
            if self.mcp_provider.lower() != "google-cloud":
                errors.append("MCP_PROVIDER must be google-cloud when REQUIRE_LIVE_ORCHESTRATION=true")
        if not self.allow_local_origins and any(
            "localhost" in origin or "127.0.0.1" in origin for origin in self.cors_origins.split(",")
        ):
            errors.append("CORS_ORIGINS must contain hosted HTTPS origins only")
        if errors:
            raise ValueError("Unsafe production configuration: " + "; ".join(errors))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


def configure_logging() -> None:
    class SecretRedactionFilter(logging.Filter):
        pattern = re.compile(
            r"(?i)(authorization|api[-_]?key|access[-_]?token|secret)(\s*[:=]\s*)([^\s,}\]]+)"
        )

        def filter(self, record: logging.LogRecord) -> bool:
            record.msg = self.pattern.sub(r"\1\2[REDACTED]", record.getMessage())
            record.args = ()
            return True

    class JsonFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            return json.dumps(
                {
                    "level": record.levelname,
                    "message": record.getMessage(),
                    "logger": record.name,
                },
                ensure_ascii=False,
            )

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(SecretRedactionFilter())
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)

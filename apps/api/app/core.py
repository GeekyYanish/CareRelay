from __future__ import annotations

import json
import logging
import re
import sys
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "CareRelay"
    demo_mode: bool = True
    seed_demo_data: bool = True
    agent_provider: str = "mock"
    orchestrator_provider: str = "local"
    retrieval_provider: str = "qdrant"
    mcp_provider: str = "mock"
    a2a_enabled: bool = True
    database_url: str = "sqlite:///./carerelay.db"
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"
    jwt_secret: str = "change-this-outside-demo"
    a2a_shared_token: str = "demo-a2a-token"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-latest"
    lyzr_api_key: str = ""
    lyzr_workflow_id: str = ""
    lyzr_api_base: str = "https://inference.studio.lyzr.ai/api"
    lyzr_timeout_seconds: float = 45.0
    lyzr_poll_interval_seconds: float = 0.5
    require_live_orchestration: bool = False
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://127.0.0.1:5174"
    public_api_base_url: str = "http://localhost:8000"
    google_cloud_project: str = ""
    google_cloud_mcp_token: str = ""
    clinical_rules_path: str = "../../../packages/clinical-rules/demo_v1.yaml"
    demo_data_path: str = "../../../packages/demo-data/scenarios.json"
    retrieval_threshold: float = 0.70
    low_risk_uncertainty_max: float = 0.25
    provider_timeout_seconds: float = 2.0

    @model_validator(mode="after")
    def reject_unsafe_production_configuration(self) -> "Settings":
        if self.demo_mode:
            return self
        errors: list[str] = []
        if self.seed_demo_data:
            errors.append("SEED_DEMO_DATA must be false")
        if self.database_url.startswith("sqlite"):
            errors.append("DATABASE_URL must use PostgreSQL")
        if len(self.jwt_secret) < 32 or self.jwt_secret == "change-this-outside-demo":
            errors.append("JWT_SECRET must contain at least 32 non-demo characters")
        if self.a2a_enabled and len(self.a2a_shared_token) < 32:
            errors.append("A2A_SHARED_TOKEN must contain at least 32 characters")
        if self.orchestrator_provider.lower() != "lyzr":
            errors.append("ORCHESTRATOR_PROVIDER must be lyzr")
        if not self.lyzr_api_key or not self.lyzr_workflow_id:
            errors.append("LYZR_API_KEY and LYZR_WORKFLOW_ID are required")
        if not self.require_live_orchestration:
            errors.append("REQUIRE_LIVE_ORCHESTRATION must be true")
        if any("localhost" in origin or "127.0.0.1" in origin for origin in self.cors_origins.split(",")):
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

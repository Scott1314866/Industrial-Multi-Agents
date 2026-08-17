from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_prefix="IMA_",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "MOLDWISE Industrial Agent Platform"
    environment: Literal["development", "test", "production"] = "development"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite+aiosqlite:///./moldwise-dev.db"
    redis_url: str = "redis://127.0.0.1:6379/0"
    milvus_host: str = "127.0.0.1"
    milvus_port: int = 19530
    milvus_database: str = "industrial_rag"
    milvus_collection: str = "injection_molding_knowledge"
    execution_mode: Literal["inline", "redis"] = "inline"
    rag_mode: Literal["fake", "a2a"] = "fake"
    rag_a2a_url: str = "http://127.0.0.1:5010"
    rag_timeout_seconds: float = 8.0
    jwt_secret: str = "development-only-secret-change-before-production"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 20
    refresh_token_days: int = 7
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    llm_api_key: str | None = None
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"
    log_level: str = "INFO"

    @field_validator("jwt_secret")
    @classmethod
    def secure_production_secret(cls, value: str, info: object) -> str:
        # Production validation is also performed at app startup after all fields are loaded.
        if len(value) < 32:
            raise ValueError("IMA_JWT_SECRET must contain at least 32 characters")
        return value

    def validate_for_startup(self) -> None:
        if self.environment == "production" and "development-only" in self.jwt_secret:
            raise RuntimeError("Production cannot use the development JWT secret")
        if self.environment == "production" and self.database_url.startswith("sqlite"):
            raise RuntimeError("Production requires a MySQL database URL")
        if self.environment == "production" and self.execution_mode != "redis":
            raise RuntimeError("Production requires the Redis worker execution mode")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_for_startup()
    return settings

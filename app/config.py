"""Настройки процесса из `.env` (ТЗ §2)."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    HUB_SECRET: str = ""
    INSTANCE_BOOTSTRAP_TOKEN: str = ""
    SESSION_SECRET: str = ""

    HOST: str = "127.0.0.1"
    PORT: int = 8080

    DATA_DIR: str = "./data"
    SQLITE_PATH: str = "./data/hub.db"
    LOG_DIR: str = "./data/logs"
    LOG_ENABLED: bool = True
    LOG_MAX_BYTES: int = 5 * 1024 * 1024
    LOG_BACKUP_COUNT: int = 5

    COOKIE_SECURE: bool = False
    DISPATCH_NO_CANDIDATE_SEC: int = 3600
    DISPATCH_POLL_SEC: float = 1.0
    WORKER_HTTP_TIMEOUT_SEC: float = 30.0
    WORKER_UPLOAD_TIMEOUT_SEC: float = 300.0

    @field_validator("LOG_MAX_BYTES")
    @classmethod
    def _positive_log_max_bytes(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("LOG_MAX_BYTES must be > 0")
        return value

    @field_validator("LOG_BACKUP_COUNT")
    @classmethod
    def _positive_log_backup_count(cls, value: int) -> int:
        if value < 1:
            raise ValueError("LOG_BACKUP_COUNT must be >= 1")
        return value

    @field_validator("DISPATCH_NO_CANDIDATE_SEC")
    @classmethod
    def _non_negative_dispatch_timeout(cls, value: int) -> int:
        if value < 0:
            raise ValueError("DISPATCH_NO_CANDIDATE_SEC must be >= 0")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()

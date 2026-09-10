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
    # Both paths required to enable HTTPS (self-signed or CA-signed PEM).
    SSL_CERTFILE: str = ""
    SSL_KEYFILE: str = ""
    SSL_KEYFILE_PASSWORD: str = ""

    DATA_DIR: str = "./data"
    # Audio blobs: local filesystem under DATA_DIR/uploads or S3-compatible object storage.
    STORAGE_BACKEND: str = "local"
    S3_ENDPOINT: str = ""
    S3_BUCKET: str = ""
    S3_REGION: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    # Per-upload SSE header. Empty = omit (use bucket default encryption).
    # AWS S3: AES256. Yandex Object Storage: aws:kms + S3_SSE_KMS_KEY_ID, or empty + bucket KMS in console.
    S3_SSE: str = ""
    S3_SSE_KMS_KEY_ID: str = ""
    DATABASE_URL: str = "sqlite:///./data/hub.db"
    SQLITE_PATH: str = "./data/hub.db"
    LOG_DIR: str = "./data/logs"
    LOG_ENABLED: bool = True
    LOG_MAX_BYTES: int = 5 * 1024 * 1024
    LOG_BACKUP_COUNT: int = 5

    COOKIE_SECURE: bool = False
    # Comma-separated IPs/CIDRs of reverse proxies allowed to set X-Forwarded-For / X-Real-IP.
    # Empty = trust none (use TCP peer only).
    TRUSTED_PROXIES: str = ""
    DISPATCH_NO_CANDIDATE_SEC: int = 3600
    DISPATCH_POLL_SEC: float = 1.0
    WORKER_HTTP_TIMEOUT_SEC: float = 30.0
    WORKER_UPLOAD_TIMEOUT_SEC: float = 300.0

    # Prometheus GET /metrics. false / 0 / no = process collectors only; endpoint stays up.
    METRICS_ENABLED: bool = True
    # Bearer token for Prometheus scrape. Empty = no auth (set in production).
    METRICS_TOKEN: str = ""

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

    @field_validator("STORAGE_BACKEND")
    @classmethod
    def _storage_backend(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"local", "s3"}:
            raise ValueError("STORAGE_BACKEND must be 'local' or 's3'")
        return normalized


@lru_cache
def get_settings() -> Settings:
    return Settings()

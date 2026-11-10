"""Application settings and configuration."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """DocuExtract configuration settings loaded from environment variables."""

    app_name: str = "DocuExtract"
    app_version: str = "0.1.0"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    host: str = "127.0.0.1"
    port: int = 8000

    # Upload constraints: default 10 MiB
    max_upload_size_bytes: int = 10 * 1024 * 1024

    # Logging configuration
    log_level: str = "INFO"
    log_json_format: bool = True

    model_config = SettingsConfigDict(
        env_prefix="DOCUEXTRACT_",
        env_file=(".env", "app/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()

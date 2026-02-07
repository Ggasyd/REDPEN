"""Application configuration using Pydantic Settings."""
import json
from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Application
    app_name: str = "REDPEN"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = True
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Database
    database_url: str
    database_echo: bool = False

    # Redis
    redis_url: str

    # Celery
    celery_broker_url: str
    celery_result_backend: str

    # Storage
    storage_type: str = "minio"  # minio or s3
    minio_endpoint: str = "minio:9000"
    minio_access_key: str
    minio_secret_key: str
    minio_secure: bool = False
    minio_bucket_name: str = "redpen-storage"

    # AWS S3
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "eu-west-1"
    s3_bucket_name: str = ""

    # AI Services
    openai_api_key: str
    google_api_key: str
    mistral_api_key: str

    # AI Models
    openai_model: str = "gpt-4o-mini"
    gemini_model: str = "gemini-1.5-flash"
    mistral_ocr_model: str = "pixtral-12b-2409"

    # CORS
    cors_origins: str = '["http://localhost:3000","http://localhost:8000"]'

    # GDPR Defaults
    default_retention_submissions_days: int = 730
    default_retention_artifacts_days: int = 365
    default_retention_ml_days: int = 365

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str) -> List[str]:
        """Parse CORS origins from JSON string."""
        if isinstance(v, str):
            return json.loads(v)
        return v


# Global settings instance
settings = Settings()

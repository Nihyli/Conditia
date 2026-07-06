from functools import lru_cache
from typing import Literal
from uuid import UUID

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from paths import DEFAULT_DB_PATH, DEFAULT_STORAGE_DIR


class Settings(BaseSettings):
    """Application configuration, loaded from environment / .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Absolute paths by default so cwd doesn't matter when starting uvicorn.
    database_url: str = f"sqlite+aiosqlite:///{DEFAULT_DB_PATH.as_posix()}"
    storage_dir: str = str(DEFAULT_STORAGE_DIR)
    storage_backend: Literal["local", "supabase"] = "local"

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    environment: Literal["development", "test", "production"] = "development"
    auth_mode: Literal["disabled", "api_key", "jwt"] = "disabled"
    api_key: str | None = None
    api_fleet_id: UUID | None = None
    jwt_secret: str | None = None
    docs_enabled: bool = True

    max_upload_bytes: int = 25 * 1024 * 1024
    max_files_per_upload: int = 6
    max_request_bytes: int = 151 * 1024 * 1024
    max_image_pixels: int = 50_000_000

    # Per-client requests per minute. 0 disables the in-process limiter; real
    # multi-instance protection still belongs at the gateway.
    rate_limit_per_minute: int = 0

    seed_on_startup: bool = False

    supabase_url: str | None = None
    supabase_key: str | None = None
    supabase_storage_bucket: str = "inspection-media"
    google_application_credentials: str | None = None

    @model_validator(mode="after")
    def validate_security_posture(self) -> "Settings":
        if self.auth_mode == "api_key" and (
            self.api_key is None or len(self.api_key) < 32
        ):
            raise ValueError("API_KEY must contain at least 32 characters")
        if self.auth_mode == "jwt" and (
            self.jwt_secret is None or len(self.jwt_secret) < 32
        ):
            raise ValueError("JWT_SECRET must contain at least 32 characters")
        if self.environment == "production":
            if self.auth_mode == "disabled":
                raise ValueError("AUTH_MODE cannot be disabled in production")
            if self.auth_mode == "api_key" and self.api_fleet_id is None:
                raise ValueError("API_FLEET_ID is required when AUTH_MODE=api_key")
            if self.auth_mode == "jwt" and self.jwt_secret is None:
                raise ValueError("JWT_SECRET is required when AUTH_MODE=jwt")
            if not self.database_url.startswith(
                ("postgresql+asyncpg://", "postgres+asyncpg://")
            ):
                raise ValueError(
                    "Production requires PostgreSQL through the asyncpg driver"
                )
            if self.storage_backend != "supabase" or not self.supabase_enabled:
                raise ValueError(
                    "Production requires Supabase storage configuration"
                )
            if self.seed_on_startup:
                raise ValueError("SEED_ON_STARTUP cannot be enabled in production")
            if self.docs_enabled:
                raise ValueError("DOCS_ENABLED must be false in production")
            if not self.cors_list or any(
                "localhost" in origin or "127.0.0.1" in origin
                for origin in self.cors_list
            ):
                raise ValueError("CORS_ORIGINS must use deployed origins in production")
        if self.max_upload_bytes < 1:
            raise ValueError("MAX_UPLOAD_BYTES must be positive")
        if self.max_request_bytes < self.max_upload_bytes:
            raise ValueError("MAX_REQUEST_BYTES cannot be smaller than MAX_UPLOAD_BYTES")
        if not 1 <= self.max_files_per_upload <= 20:
            raise ValueError("MAX_FILES_PER_UPLOAD must be between 1 and 20")
        if self.max_image_pixels < 1:
            raise ValueError("MAX_IMAGE_PIXELS must be positive")
        if self.rate_limit_per_minute < 0:
            raise ValueError("RATE_LIMIT_PER_MINUTE cannot be negative")
        return self

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def google_vision_enabled(self) -> bool:
        return bool(self.google_application_credentials)

    @property
    def supabase_enabled(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

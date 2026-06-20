from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, loaded from environment / .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Async SQLAlchemy URL. SQLite by default; swap to postgresql+asyncpg for Supabase.
    database_url: str = "sqlite+aiosqlite:///./conditia.db"

    # Local-dev media storage root (used by LocalStorageService).
    storage_dir: str = "./storage"

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    seed_on_startup: bool = False

    # Optional production integrations.
    supabase_url: str | None = None
    supabase_key: str | None = None
    google_application_credentials: str | None = None

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

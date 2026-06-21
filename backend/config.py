from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from paths import DEFAULT_DB_PATH, DEFAULT_STORAGE_DIR


class Settings(BaseSettings):
    """Application configuration, loaded from environment / .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Absolute paths by default so cwd doesn't matter when starting uvicorn.
    database_url: str = f"sqlite+aiosqlite:///{DEFAULT_DB_PATH.as_posix()}"
    storage_dir: str = str(DEFAULT_STORAGE_DIR)

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    seed_on_startup: bool = False

    # Allow POST /admin/seed and /admin/unseed (disable in production).
    admin_enabled: bool = True

    # Auth — local JWT by default; set SUPABASE_URL + SUPABASE_JWT_SECRET for Supabase Auth.
    auth_enabled: bool = True
    jwt_secret: str = "change-me-in-production-use-openssl-rand"
    jwt_expire_hours: int = 24
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_jwt_secret: str | None = None
    supabase_key: str | None = None
    # auto | local | supabase — set AUTH_PROVIDER=local for demo accounts during dev
    auth_provider_setting: str = Field(default="auto", validation_alias="AUTH_PROVIDER")
    google_application_credentials: str | None = None

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def auth_provider(self) -> str:
        mode = self.auth_provider_setting.lower().strip()
        if mode == "local":
            return "local"
        if mode == "supabase":
            return "supabase"
        # auto — need URL, JWT secret, and anon key for client-side Supabase Auth
        if self.supabase_url and self.supabase_jwt_secret and self.supabase_anon_key:
            return "supabase"
        return "local"

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

"""Application configuration using pydantic-settings."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseModel):
    path: Path = Path(__file__).parent.parent.parent / "data" / "nexora.db"


class ServerSettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8765
    log_level: str = "INFO"


class SecuritySettings(BaseModel):
    local_only: bool = False
    conversation_storage: bool = True
    secure_logging: bool = True


class UISettings(BaseModel):
    theme: str = "dark"
    reduced_motion: bool = False
    hud_density: str = "normal"
    fullscreen: bool = False


class AIGlobals(BaseModel):
    default_temperature: float = 0.7
    default_context: int = 4096
    streaming: bool = True
    offline_fallback_enabled: bool = True


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__", env_file=".env")

    database: DatabaseSettings = DatabaseSettings()
    server: ServerSettings = ServerSettings()
    security: SecuritySettings = SecuritySettings()
    ui: UISettings = UISettings()
    ai: AIGlobals = AIGlobals()


settings = Settings()

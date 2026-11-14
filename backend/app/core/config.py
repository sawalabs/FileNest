import os
import sys
from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_default_data_dir() -> Path:
    if os.environ.get("FILENEST_DATA_DIR"):
        return Path(os.environ["FILENEST_DATA_DIR"])
    if getattr(sys, "frozen", False) or os.environ.get("ENVIRONMENT") == "production":
        local_app_data = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(local_app_data) / "FileNest" / "data"
    return Path("./data")


def get_default_db_url() -> str:
    db_file = get_default_data_dir() / "desktop_storage_manager.db"
    return f"sqlite:///{db_file.as_posix()}"


class Settings(BaseSettings):
    PROJECT_NAME: str = "Desktop & Storage Manager"
    VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"
    
    # Database configuration
    DATABASE_URL: str = Field(default_factory=get_default_db_url)
    
    # Server configuration
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    ENVIRONMENT: str = "production"
    LOG_LEVEL: str = "INFO"
    
    # Allowed CORS origins for Tauri and local dev
    CORS_ORIGINS: list[str] = [
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "tauri://localhost",
        "http://tauri.localhost",
        "https://tauri.localhost",
    ]

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v.startswith("sqlite:///"):
            raise ValueError("DATABASE_URL must be an SQLite URI starting with 'sqlite:///'")
        return v

    @field_validator("PORT")
    @classmethod
    def validate_port(cls, v: int) -> int:
        if not (1 <= v <= 65535):
            raise ValueError("PORT must be between 1 and 65535")
        return v

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid:
            raise ValueError(f"LOG_LEVEL must be one of {valid}")
        return v.upper()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

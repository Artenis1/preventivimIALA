from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = (
        "postgresql+psycopg://smartestimate:smartestimate@localhost:5432/smartestimate"
    )
    storage_dir: str = str(Path(__file__).resolve().parents[2] / "storage")
    cookie_secure: bool = False
    session_hours: int = 24
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    max_upload_mb: int = 15
    ai_base_url: str = "https://api.openai.com/v1"
    ai_api_key: str = ""
    ai_model: str = ""
    embedding_model: str = ""
    high_confidence: float = 0.93
    medium_confidence: float = 0.65


@lru_cache
def get_settings():
    return Settings()

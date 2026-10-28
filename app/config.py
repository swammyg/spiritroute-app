"""Runtime configuration, read from environment variables and an optional .env file."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.schemas import Driver, Emotion

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Embeddings (spec section 3)
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # Vector store: embedded Qdrant at qdrant_path unless qdrant_url is set
    qdrant_url: str | None = None
    qdrant_api_key: str | None = None
    qdrant_path: Path = PROJECT_ROOT / "data" / "qdrant"
    qdrant_collection: str = "scriptures"

    # Light LLM via Ollama (spec section 6)
    llm_enabled: bool = True
    ollama_base_url: str = "http://localhost:11434"
    llm_model: str = "llama3.2:3b"
    llm_temperature: float = 0.4
    llm_timeout_seconds: float = 60.0
    llm_max_attempts: int = Field(default=2, ge=1)
    llm_max_output_tokens: int = 400
    llm_max_words: int = 150

    # Search: subtract the mean of the 64 possible query vectors before searching (see query_vectors.py)
    query_centering: bool = True

    # HTTP
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # Safety (spec section 7): wizard answers that trigger the crisis override on their own
    crisis_selection_triggers: list[tuple[Emotion, Driver]] = Field(default_factory=list)

    @field_validator("qdrant_url", "qdrant_api_key", mode="before")
    @classmethod
    def _blank_means_unset(cls, value: object) -> object:
        # `QDRANT_URL=` in a .env file arrives as "", which must behave like "not set".
        return None if value == "" else value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

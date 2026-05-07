"""Central settings + startup environment validation.

A single Settings object loaded once via pydantic-settings. Imported by every
module that needs an env variable so we never sprinkle os.getenv calls.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Populate os.environ from .env so libraries that read os.environ directly
# (e.g. langchain-anthropic's ChatAnthropic looking for ANTHROPIC_API_KEY)
# also see the values. pydantic-settings only fills the Settings object —
# it does NOT export to the process environment.
load_dotenv(PROJECT_ROOT / ".env", override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- LLM ---
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    # Defaults to the current Haiku. Override via CHAT_MODEL in .env if you
    # want Sonnet ("claude-sonnet-4-6") or Opus ("claude-opus-4-6").
    chat_model: str = Field(default="claude-haiku-4-5-20251001", alias="CHAT_MODEL")

    # --- IT Ops API ---
    it_ops_api_url: str = Field(default="http://localhost:8001", alias="IT_OPS_API_URL")
    it_ops_api_token: str = Field(
        default="dev-local-only-token", alias="IT_OPS_API_TOKEN"
    )
    it_ops_db_path: str = Field(
        default=str(PROJECT_ROOT / "services" / "it_ops_api" / "it_ops.db"),
        alias="IT_OPS_DB_PATH",
    )

    # --- RAG ---
    chroma_db_path: str = Field(
        default=str(PROJECT_ROOT / "chroma_db"), alias="CHROMA_DB_PATH"
    )
    kb_dir: str = Field(
        default=str(PROJECT_ROOT / "backend" / "data" / "kb"), alias="KB_DIR"
    )
    rag_distance_threshold: float = Field(default=0.85, alias="RAG_DISTANCE_THRESHOLD")
    embedding_model: str = Field(default="all-MiniLM-L6-v2", alias="EMBEDDING_MODEL")

    # --- App ---
    env: str = Field(default="dev", alias="ENV")
    allowed_origins: str = Field(
        default="http://localhost:5173", alias="ALLOWED_ORIGINS"
    )
    enable_debug_endpoints: bool = Field(default=True, alias="ENABLE_DEBUG_ENDPOINTS")

    @field_validator("rag_distance_threshold")
    @classmethod
    def _bounded_threshold(cls, v: float) -> float:
        if v <= 0 or v > 2.0:
            raise ValueError("RAG_DISTANCE_THRESHOLD must be between 0 and 2.0")
        return v

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def is_prod(self) -> bool:
        return self.env.lower() in {"prod", "production"}

    def validate_runtime(self, *, require_llm: bool = True) -> list[str]:
        """Return a list of human-readable problems for whoever is starting up."""
        problems: list[str] = []
        if require_llm and not self.anthropic_api_key:
            problems.append(
                "ANTHROPIC_API_KEY is not set — copy .env.example to .env and fill it in."
            )
        if self.is_prod and self.it_ops_api_token in ("", "dev-local-only-token"):
            problems.append(
                "IT_OPS_API_TOKEN is unset or still the default in production."
            )
        if not Path(self.kb_dir).exists():
            problems.append(f"KB_DIR does not exist: {self.kb_dir}")
        return problems


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

"""Central typed settings, loaded from PHA_-prefixed environment variables or backend/.env."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from pha.offline import is_loopback_host, url_host

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PHA_", env_file=".env", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8000
    ollama_url: str = "http://127.0.0.1:11434"
    # Grounded LoRA v2: matches or beats phi3-base on the grounding probe (training/model_card.md).
    # v1 "phi3-medquad" ignores retrieved documents; never make it the default.
    model: str = "phi3-medquad-v2"
    llm_backend: Literal["ollama", "fake"] = "ollama"
    num_ctx: int = 4096  # Phi-3-mini-4k context window
    num_predict: int = 768  # max new tokens per answer
    temperature: float = 0.2
    llm_timeout_s: float = 120.0
    system_prompt_path: Path = REPO_ROOT / "training" / "system_prompt.txt"
    chroma_dir: Path = REPO_ROOT / "data" / "chroma"
    uploads_dir: Path = REPO_ROOT / "data" / "uploads"
    embed_model_dir: Path = REPO_ROOT / "models" / "embeddings" / "bge-small-en-v1.5"
    frontend_dist: Path = REPO_ROOT / "frontend" / "dist"
    registry_path: Path = REPO_ROOT / "data" / "documents.json"
    chats_path: Path = REPO_ROOT / "data" / "chats.db"

    # RAG tuning
    chunk_size: int = 800  # characters
    chunk_overlap: int = 120
    top_k: int = 4
    min_score: float = 0.50  # cosine similarity (BGE scores are compressed); tune in eval suite
    max_upload_bytes: int = 20 * 1024 * 1024

    @model_validator(mode="after")
    def _enforce_loopback(self) -> "Settings":
        if not is_loopback_host(self.host):
            raise ValueError(
                f"PHA_HOST={self.host!r} is not allowed: the backend may only bind to a "
                "loopback address (127.0.0.1, ::1, or localhost) so it is never exposed "
                "to the network."
            )
        if not is_loopback_host(url_host(self.ollama_url)):
            raise ValueError(
                f"PHA_OLLAMA_URL={self.ollama_url!r} is not allowed: the model server must be "
                "local (e.g. http://127.0.0.1:11434) so queries never leave this machine."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

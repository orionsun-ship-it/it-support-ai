"""Sentence-transformers wrapper. The model is loaded once per process."""

from __future__ import annotations

from functools import lru_cache

from backend.config import get_settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class Embedder:
    """Lazy-loaded embedding model. Use Embedder.shared() to reuse a singleton."""

    _instance: Embedder | None = None

    def __init__(self) -> None:
        settings = get_settings()
        self.model_name = settings.embedding_model
        try:
            from sentence_transformers import SentenceTransformer

            self.model = SentenceTransformer(self.model_name)
            logger.info("Loaded embedding model %s", self.model_name)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"Failed to load sentence-transformers model '{self.model_name}'. "
                f"Underlying error: {exc}"
            ) from exc

    @classmethod
    def shared(cls) -> Embedder:
        """Return a process-wide singleton — the model is heavy to load."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def embed_text(self, text: str) -> list[float]:
        return self.model.encode(text, convert_to_numpy=True).tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(texts, convert_to_numpy=True)
        return [v.tolist() for v in vectors]


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    return Embedder.shared()

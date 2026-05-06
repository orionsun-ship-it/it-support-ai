"""Sentence-transformers wrapper used to produce embeddings for the RAG pipeline."""

from __future__ import annotations

from backend.utils.logger import get_logger

logger = get_logger(__name__)

MODEL_NAME = "all-MiniLM-L6-v2"


class Embedder:
    """Wraps a sentence-transformers model and exposes a tiny embedding API."""

    def __init__(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer

            self.model = SentenceTransformer(MODEL_NAME)
            logger.info("Loaded embedding model %s", MODEL_NAME)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"Failed to load sentence-transformers model '{MODEL_NAME}'. "
                f"Make sure the package is installed and the model can be downloaded. "
                f"Underlying error: {exc}"
            ) from exc

    def embed_text(self, text: str) -> list[float]:
        """Return the embedding vector for a single string."""
        vector = self.model.encode(text, convert_to_numpy=True)
        return vector.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Return embedding vectors for a batch of strings."""
        vectors = self.model.encode(texts, convert_to_numpy=True)
        return [v.tolist() for v in vectors]

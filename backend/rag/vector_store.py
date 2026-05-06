"""ChromaDB-backed vector store for the IT support knowledge base."""

from __future__ import annotations

import os

from dotenv import load_dotenv

from backend.rag.embedder import Embedder
from backend.utils.logger import get_logger

load_dotenv()
logger = get_logger(__name__)


class VectorStore:
    """A thin wrapper around a persistent ChromaDB collection."""

    def __init__(self, collection_name: str = "it_knowledge_base") -> None:
        try:
            import chromadb
        except ImportError as exc:
            raise RuntimeError(
                "chromadb is not installed. Run `pip install chromadb`."
            ) from exc

        db_path = os.getenv("CHROMA_DB_PATH", "./chroma_db")
        try:
            self.client = chromadb.PersistentClient(path=db_path)
            self.collection = self.client.get_or_create_collection(name=collection_name)
            logger.info(
                "ChromaDB ready: path=%s collection=%s count=%d",
                db_path,
                collection_name,
                self.collection.count(),
            )
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"Failed to initialize ChromaDB at path '{db_path}'. "
                f"Underlying error: {exc}"
            ) from exc

        self.embedder = Embedder()

    def add_documents(self, documents: list[dict]) -> None:
        """Upsert a list of {'id', 'text', 'metadata'} documents into the collection."""
        if not documents:
            return

        ids = [str(d["id"]) for d in documents]
        texts = [d["text"] for d in documents]
        metadatas = [d.get("metadata", {}) or {} for d in documents]
        embeddings = self.embedder.embed_batch(texts)

        self.collection.upsert(
            ids=ids,
            documents=texts,
            metadatas=metadatas,
            embeddings=embeddings,
        )
        logger.info("Upserted %d documents into the knowledge base", len(documents))

    def query(self, query_text: str, n_results: int = 3) -> list[dict]:
        """Return the top-k matching documents along with metadata and distance."""
        embedding = self.embedder.embed_text(query_text)
        result = self.collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
        )

        out: list[dict] = []
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        ids = (result.get("ids") or [[]])[0]

        for i in range(len(documents)):
            out.append(
                {
                    "id": ids[i] if i < len(ids) else None,
                    "text": documents[i],
                    "metadata": metadatas[i] if i < len(metadatas) else {},
                    "distance": distances[i] if i < len(distances) else None,
                }
            )
        return out

    def count(self) -> int:
        """Return the number of documents currently in the collection."""
        return self.collection.count()

    def delete_collection(self) -> None:
        """Delete the underlying collection. Used by tests for cleanup."""
        name = self.collection.name
        self.client.delete_collection(name=name)
        logger.info("Deleted collection %s", name)

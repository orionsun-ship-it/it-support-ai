"""ChromaDB-backed vector store for the IT support knowledge base.

Resilient to incompatible on-disk stores left over from a previous Chroma
version: if the collection metadata can't be parsed (e.g. KeyError: '_type'
seen with chromadb 0.5.13 reading older 0.4.x stores), the store is wiped
and recreated. KB content lives in JSON files on disk, so wiping the index
is always safe — the next ingest call rebuilds it.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from backend.config import get_settings
from backend.rag.embedder import get_embedder
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class VectorStore:
    """Thin wrapper around a persistent ChromaDB collection."""

    def __init__(self, collection_name: str = "it_knowledge_base") -> None:
        self.collection_name = collection_name
        self.embedder = get_embedder()
        try:
            self._initialize()
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            if self._looks_like_incompatible_store(exc, msg):
                logger.warning(
                    "Chroma store at %s appears incompatible (%s). "
                    "Wiping and rebuilding — KB content will be re-ingested.",
                    get_settings().chroma_db_path,
                    msg or type(exc).__name__,
                )
                self._reset_and_initialize()
            else:
                raise RuntimeError(
                    f"Failed to initialize ChromaDB at "
                    f"'{get_settings().chroma_db_path}'. Underlying error: {exc}"
                ) from exc

    @staticmethod
    def _looks_like_incompatible_store(exc: Exception, msg: str) -> bool:
        if isinstance(exc, KeyError) and "_type" in str(exc):
            return True
        haystack = msg.lower()
        return any(
            sig in haystack
            for sig in ("_type", "configuration", "from_json", "migrate")
        )

    def _initialize(self) -> None:
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
        except ImportError as exc:
            raise RuntimeError(
                "chromadb is not installed. Run `pip install chromadb`."
            ) from exc

        settings = get_settings()
        self.client = chromadb.PersistentClient(
            path=settings.chroma_db_path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(name=self.collection_name)
        logger.info(
            "ChromaDB ready: path=%s collection=%s count=%d",
            settings.chroma_db_path,
            self.collection_name,
            self.collection.count(),
        )

    def _reset_and_initialize(self) -> None:
        path = Path(get_settings().chroma_db_path)
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
        self._initialize()

    # -- mutation ---------------------------------------------------------

    def upsert(
        self,
        *,
        ids: list[str],
        texts: list[str],
        metadatas: list[dict],
    ) -> None:
        if not ids:
            return
        embeddings = self.embedder.embed_batch(texts)
        self.collection.upsert(
            ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings
        )
        logger.info("Upserted %d chunks", len(ids))

    def delete(self, ids: list[str]) -> None:
        if not ids:
            return
        self.collection.delete(ids=ids)
        logger.info("Deleted %d chunks", len(ids))

    # -- read -------------------------------------------------------------

    def get_all_metadata(self) -> list[dict]:
        try:
            data = self.collection.get(include=["metadatas"])
        except Exception:  # noqa: BLE001
            return []
        ids = data.get("ids") or []
        metas = data.get("metadatas") or []
        out = []
        for i, mid in enumerate(ids):
            out.append({"id": mid, "metadata": metas[i] if i < len(metas) else {}})
        return out

    def query(
        self,
        query_text: str,
        n_results: int = 3,
        where: dict | None = None,
    ) -> list[dict]:
        embedding = self.embedder.embed_text(query_text)
        result = self.collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
            where=where,
        )
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        ids = (result.get("ids") or [[]])[0]
        out = []
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
        return self.collection.count()

    def delete_collection(self) -> None:
        name = self.collection.name
        self.client.delete_collection(name=name)
        logger.info("Deleted collection %s", name)

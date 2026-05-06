"""KB ingestion pipeline.

Reads JSON document files under settings.kb_dir, chunks each body, hashes the
content, and incrementally upserts only changed/new chunks into Chroma. Chunks
whose source doc has been removed from disk are deleted from the collection.

Run directly to (re-)ingest:

    python -m backend.rag.ingest
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

from backend.config import get_settings
from backend.rag.vector_store import VectorStore
from backend.utils.logger import get_logger

logger = get_logger(__name__)

CHUNK_SIZE = 600  # characters
CHUNK_OVERLAP = 80


def _chunk(body: str) -> list[str]:
    """Naive char-window chunker with overlap. Good enough for short KB docs."""
    if len(body) <= CHUNK_SIZE:
        return [body]
    chunks: list[str] = []
    start = 0
    while start < len(body):
        end = min(start + CHUNK_SIZE, len(body))
        chunks.append(body[start:end])
        if end == len(body):
            break
        start = end - CHUNK_OVERLAP
    return chunks


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _iter_kb_files(kb_dir: Path) -> Iterable[Path]:
    for p in sorted(kb_dir.glob("*.json")):
        yield p


def _load_documents(kb_dir: Path) -> list[dict]:
    docs: list[dict] = []
    for path in _iter_kb_files(kb_dir):
        try:
            payload = json.loads(path.read_text())
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping %s: %s", path, exc)
            continue
        # Each KB file may contain a single doc or a {documents: [...]} envelope.
        if isinstance(payload, dict) and "documents" in payload:
            for d in payload["documents"]:
                d["_source_file"] = path.name
                docs.append(d)
        elif isinstance(payload, dict):
            payload["_source_file"] = path.name
            docs.append(payload)
        elif isinstance(payload, list):
            for d in payload:
                d["_source_file"] = path.name
                docs.append(d)
    return docs


def ingest(*, force: bool = False) -> dict:
    """Idempotent ingest. Returns a small summary dict."""
    settings = get_settings()
    kb_dir = Path(settings.kb_dir)
    kb_dir.mkdir(parents=True, exist_ok=True)

    store = VectorStore()
    existing = store.get_all_metadata()
    existing_by_id = {row["id"]: row["metadata"] or {} for row in existing}

    docs = _load_documents(kb_dir)
    if not docs:
        logger.warning("No KB documents found under %s", kb_dir)
        return {"upserted": 0, "deleted": 0, "skipped": 0, "total_chunks": 0}

    desired_ids: set[str] = set()
    upsert_ids: list[str] = []
    upsert_texts: list[str] = []
    upsert_meta: list[dict] = []
    skipped = 0

    for doc in docs:
        doc_id = doc.get("doc_id") or doc.get("id")
        if not doc_id:
            logger.warning("Document missing doc_id, skipping: %s", doc.get("title"))
            continue
        body = doc.get("body") or doc.get("text") or ""
        if not body:
            continue

        title = doc.get("title", doc_id)
        category = doc.get("category", "other")
        source = doc.get("source", "internal-kb")
        version = doc.get("version", "")
        updated_at = doc.get("updated_at") or datetime.utcnow().isoformat()

        for idx, chunk in enumerate(_chunk(body)):
            chunk_id = f"{doc_id}::chunk-{idx}"
            content_hash = _hash(chunk)
            desired_ids.add(chunk_id)

            existing_meta = existing_by_id.get(chunk_id, {})
            if not force and existing_meta.get("content_hash") == content_hash:
                skipped += 1
                continue

            metadata = {
                "doc_id": doc_id,
                "chunk_id": chunk_id,
                "chunk_index": idx,
                "title": title,
                "category": category,
                "source": source,
                "version": version,
                "updated_at": updated_at,
                "content_hash": content_hash,
            }
            upsert_ids.append(chunk_id)
            upsert_texts.append(chunk)
            upsert_meta.append(metadata)

    # Delete chunks whose source doc has been removed.
    to_delete = [cid for cid in existing_by_id if cid not in desired_ids]

    if upsert_ids:
        store.upsert(ids=upsert_ids, texts=upsert_texts, metadatas=upsert_meta)
    if to_delete:
        store.delete(to_delete)

    summary = {
        "upserted": len(upsert_ids),
        "deleted": len(to_delete),
        "skipped": skipped,
        "total_chunks": store.count(),
    }
    logger.info(
        "Ingestion complete: upserted=%d deleted=%d skipped=%d total=%d",
        summary["upserted"],
        summary["deleted"],
        summary["skipped"],
        summary["total_chunks"],
    )
    return summary


if __name__ == "__main__":  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Re-ingest every chunk")
    args = parser.parse_args()
    print(ingest(force=args.force))

"""High-level retrieval API with a quality threshold.

Returns structured `RetrievalResult` with a `match_strength` flag so the
knowledge agent can take the right path (cite KB vs. ask for clarification).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from backend.config import get_settings
from backend.rag.ingest import ingest
from backend.rag.vector_store import VectorStore
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Useful token regex for "must include" keyword fallbacks (error codes etc).
_KEYWORD_PATTERNS = [
    re.compile(r"\b1603\b"),
    re.compile(r"\b0x[0-9A-Fa-f]{8}\b"),
    re.compile(r"\bPAGE_FAULT_IN_NONPAGED_AREA\b", re.IGNORECASE),
]


@dataclass
class KBSource:
    doc_id: str
    title: str
    category: str
    distance: float
    snippet: str
    chunk_id: str = ""

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "category": self.category,
            "score": round(1.0 - min(self.distance, 1.0), 3),
            "distance": round(self.distance, 4),
            "snippet": self.snippet,
            "chunk_id": self.chunk_id,
        }


@dataclass
class RetrievalResult:
    query: str
    match_strength: Literal["strong", "weak", "none"]
    sources: list[KBSource] = field(default_factory=list)
    raw: list[dict] = field(default_factory=list)

    @property
    def has_strong_match(self) -> bool:
        return self.match_strength == "strong"


class KnowledgeRetriever:
    """Retrieves KB chunks with a distance threshold and category filtering."""

    def __init__(self) -> None:
        self.store = VectorStore()
        self.threshold = get_settings().rag_distance_threshold

    def count(self) -> int:
        return self.store.count()

    def retrieve(
        self,
        query: str,
        n_results: int = 3,
        *,
        category: str | None = None,
    ) -> RetrievalResult:
        where = {"category": category} if category and category != "other" else None
        try:
            raw = self.store.query(query, n_results=n_results, where=where)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Vector query failed: %s", exc)
            raw = []

        # If the category filter returned nothing, retry without it.
        if not raw and where is not None:
            try:
                raw = self.store.query(query, n_results=n_results)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Fallback vector query failed: %s", exc)
                raw = []

        # Keyword-rescue: if the query mentions a known error token but the
        # top hit is far, try filtering by category="software" or scanning for
        # hits that contain that token.
        keyword_hits = self._keyword_rescue(query, raw)
        if keyword_hits:
            raw = keyword_hits + [r for r in raw if r not in keyword_hits]

        sources: list[KBSource] = []
        for r in raw:
            md = r.get("metadata") or {}
            text = r.get("text") or ""
            sources.append(
                KBSource(
                    doc_id=md.get("doc_id", ""),
                    title=md.get("title", ""),
                    category=md.get("category", ""),
                    distance=float(r.get("distance") or 1.0),
                    snippet=text[:240],
                    chunk_id=md.get("chunk_id", r.get("id", "")),
                )
            )

        if not sources:
            strength: Literal["strong", "weak", "none"] = "none"
        elif sources[0].distance <= self.threshold:
            strength = "strong"
        else:
            strength = "weak"

        return RetrievalResult(
            query=query, match_strength=strength, sources=sources, raw=raw
        )

    def _keyword_rescue(self, query: str, current: list[dict]) -> list[dict]:
        if not any(p.search(query) for p in _KEYWORD_PATTERNS):
            return []
        # If the top result already contains a matching keyword, we're fine.
        if current and any(
            p.search(current[0].get("text", "")) for p in _KEYWORD_PATTERNS
        ):
            return []
        # Otherwise scan for any chunk that contains the keyword token.
        out: list[dict] = []
        for r in current:
            text = r.get("text", "")
            if any(p.search(text) for p in _KEYWORD_PATTERNS):
                out.append(r)
        return out

    @staticmethod
    def format_context(result: RetrievalResult) -> str:
        if not result.sources:
            return "(no knowledge base entries matched this query)"
        lines = ["Relevant Knowledge Base Entries:"]
        for i, s in enumerate(result.sources, start=1):
            lines.append(f"{i}. [{s.doc_id}] {s.title}: {s.snippet}")
        return "\n".join(lines)


def seed_knowledge_base(*, force: bool = False) -> dict:
    """Run the file-based ingestion. Idempotent — safe to call on every startup."""
    return ingest(force=force)

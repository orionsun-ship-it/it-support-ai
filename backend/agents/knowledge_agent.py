"""Knowledge agent — two clear paths based on retrieval strength."""

from __future__ import annotations

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from backend.config import get_settings
from backend.rag.retriever import KnowledgeRetriever, RetrievalResult
from backend.utils.logger import get_logger

logger = get_logger(__name__)

GROUNDED_PROMPT = """\
You are an IT support assistant. Answer the user's question using ONLY the
knowledge base context provided. Cite each step you take from a specific
[doc_id]. If a step is not supported by the context, do not include it.
Keep the answer concise and actionable.
"""

NO_MATCH_PROMPT = """\
You are an IT support assistant. The internal knowledge base does NOT contain
documentation for this issue. Do NOT invent procedures. Instead:

1. Acknowledge that the KB does not cover this specific issue.
2. Ask ONE concise clarifying question that would help route the issue.
3. Tell the user a ticket can be opened so a human technician follows up.

Do not include step-by-step troubleshooting. Keep it short.
"""


class KnowledgeAgent:
    """Retrieves KB chunks then asks Claude Haiku to write the answer."""

    def __init__(self) -> None:
        settings = get_settings()
        self.llm = ChatAnthropic(
            model=settings.chat_model,
            temperature=0.2,
            anthropic_api_key=settings.anthropic_api_key or None,
        )
        self.retriever = KnowledgeRetriever()

    def run(self, state: dict) -> dict:
        user_message = state.get("user_message", "")
        intent = state.get("intent") or ""
        category = state.get("category") or "other"
        confidence = float(state.get("confidence") or 0.0)

        query = f"{user_message} {intent}".strip()
        category_filter = category if confidence >= 0.7 else None

        try:
            result: RetrievalResult = self.retriever.retrieve(
                query, n_results=3, category=category_filter
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("KB retrieval failed: %s", exc)
            result = RetrievalResult(query=query, match_strength="none")

        state["context"] = KnowledgeRetriever.format_context(result)
        state["context_scores"] = [s.to_dict() for s in result.sources]
        state["match_strength"] = result.match_strength
        state["sources"] = [s.to_dict() for s in result.sources]

        if result.has_strong_match:
            system = GROUNDED_PROMPT
            user_payload = (
                f"{state['context']}\n\n"
                f"User question: {user_message}\n\n"
                f"Answer using citations like [doc_id] for each step."
            )
        else:
            system = NO_MATCH_PROMPT
            user_payload = (
                f"User question: {user_message}\n\n"
                f"Closest (but weak) KB matches for context only:\n"
                f"{state['context']}"
            )

        try:
            response = self.llm.invoke(
                [SystemMessage(content=system), HumanMessage(content=user_payload)]
            )
            content = (
                response.content
                if isinstance(response.content, str)
                else str(response.content)
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "KnowledgeAgent LLM call failed (%s): %s", type(exc).__name__, exc
            )
            content = (
                "I couldn't reach Claude just now. This usually means the "
                "ANTHROPIC_API_KEY in your .env is missing or invalid — check "
                "the backend logs for the exact error. I'll route this to a "
                "human if you'd like."
            )

        state["response"] = content
        return state

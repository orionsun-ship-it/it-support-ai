"""Knowledge agent — answers using ONLY content retrieved from the vector store."""

from __future__ import annotations

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from backend.rag.retriever import KnowledgeRetriever
from backend.utils.logger import get_logger

load_dotenv()
logger = get_logger(__name__)

KNOWLEDGE_SYSTEM_PROMPT = (
    "You are an IT support assistant. Use ONLY the provided knowledge base context to "
    "answer the user's question. If the context does not contain relevant information, "
    "say: 'I don't have specific documentation for this issue, but here is general "
    "guidance:' and then give general advice. Keep answers concise and actionable."
)


class KnowledgeAgent:
    """Retrieves KB entries and asks Claude Haiku to write a grounded answer."""

    def __init__(self) -> None:
        self.llm = ChatAnthropic(model="claude-3-5-haiku-20241022", temperature=0.2)
        self.retriever = KnowledgeRetriever()

    def run(self, state: dict) -> dict:
        user_message = state.get("user_message", "")
        intent = state.get("intent") or ""
        query = f"{user_message} {intent}".strip()

        try:
            context = self.retriever.retrieve(query, n_results=3)
            scores = self.retriever.retrieve_with_scores(query, n_results=3)
        except Exception as exc:  # noqa: BLE001
            logger.warning("KnowledgeAgent retrieval failed: %s", exc)
            context = "Relevant Knowledge Base Entries:\n(no results)"
            scores = []

        state["context"] = context
        state["context_scores"] = scores

        try:
            full_prompt = (
                f"{context}\n\n"
                f"User question: {user_message}"
            )
            response = self.llm.invoke(
                [
                    SystemMessage(content=KNOWLEDGE_SYSTEM_PROMPT),
                    HumanMessage(content=full_prompt),
                ]
            )
            content = response.content if isinstance(response.content, str) else str(response.content)
        except Exception as exc:  # noqa: BLE001
            logger.warning("KnowledgeAgent LLM call failed: %s", exc)
            content = (
                "I don't have specific documentation for this issue, but here is "
                "general guidance: please describe your issue with as much detail as "
                "possible (error messages, steps to reproduce) so we can help further."
            )

        state["response"] = content
        return state

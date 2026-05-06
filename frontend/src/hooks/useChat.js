import { useCallback, useState } from "react";

function uuid() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/**
 * useChat — manages a conversational message list backed by POST /api/chat.
 *
 * Each message has the shape:
 *   { id, role, content, agentName, ticketId, escalated, timestamp }
 */
export default function useChat(sessionId) {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);

  const sendMessage = useCallback(
    async (text) => {
      const trimmed = (text ?? "").trim();
      if (!trimmed) return;

      const userMessage = {
        id: uuid(),
        role: "user",
        content: trimmed,
        agentName: null,
        ticketId: null,
        escalated: false,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMessage]);
      setIsLoading(true);

      try {
        const resp = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: trimmed,
            session_id: sessionId,
          }),
        });

        if (!resp.ok) {
          const errText = await resp.text().catch(() => "");
          throw new Error(`Backend error ${resp.status}: ${errText}`);
        }

        const data = await resp.json();
        const assistantMessage = {
          id: uuid(),
          role: "assistant",
          content: data.content ?? "(empty response)",
          agentName: data.agent_name ?? "agent",
          ticketId: data.ticket_id ?? null,
          escalated: Boolean(data.escalated),
          timestamp: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, assistantMessage]);
      } catch (err) {
        setMessages((prev) => [
          ...prev,
          {
            id: uuid(),
            role: "assistant",
            content:
              "Sorry — something went wrong contacting the backend. " +
              (err && err.message ? err.message : ""),
            agentName: "error",
            ticketId: null,
            escalated: false,
            timestamp: new Date().toISOString(),
          },
        ]);
      } finally {
        setIsLoading(false);
      }
    },
    [sessionId]
  );

  return { sessionId, messages, isLoading, sendMessage };
}

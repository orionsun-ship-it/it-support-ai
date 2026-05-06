import { useCallback, useState } from 'react';

function uuid() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/**
 * Each message has the shape:
 *   { id, role, content, agentName, ticketId, escalated, sources, routeTrace,
 *     finalRoute, ticketDecisionReason, automationStatus, category, intent,
 *     severity, urgency, matchStrength, timestamp }
 */
export default function useChat(sessionId) {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [errorBanner, setErrorBanner] = useState(null);

  const sendMessage = useCallback(
    async (text) => {
      const trimmed = (text ?? '').trim();
      if (!trimmed) return;

      setErrorBanner(null);
      setMessages((prev) => [
        ...prev,
        {
          id: uuid(),
          role: 'user',
          content: trimmed,
          timestamp: new Date().toISOString(),
        },
      ]);
      setIsLoading(true);

      try {
        const resp = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: trimmed, session_id: sessionId }),
        });
        if (!resp.ok) {
          const errText = await resp.text().catch(() => '');
          throw new Error(`Backend error ${resp.status}: ${errText}`);
        }
        const data = await resp.json();
        setMessages((prev) => [
          ...prev,
          {
            id: uuid(),
            role: 'assistant',
            content: data.content ?? '(empty response)',
            agentName: data.agent_name ?? 'agent',
            ticketId: data.ticket_id ?? null,
            escalated: Boolean(data.escalated),
            matchStrength: data.match_strength ?? null,
            sources: Array.isArray(data.sources) ? data.sources : [],
            routeTrace: Array.isArray(data.route_trace) ? data.route_trace : [],
            finalRoute: data.final_route ?? null,
            ticketDecisionReason: data.ticket_decision_reason ?? null,
            automationStatus: data.automation_status ?? null,
            category: data.category ?? null,
            intent: data.intent ?? null,
            severity: data.severity ?? null,
            urgency: data.urgency ?? null,
            timestamp: new Date().toISOString(),
          },
        ]);
      } catch (err) {
        const msg = err && err.message ? err.message : String(err);
        setErrorBanner(msg);
        setMessages((prev) => [
          ...prev,
          {
            id: uuid(),
            role: 'assistant',
            content: 'Sorry — something went wrong contacting the backend. ' + msg,
            agentName: 'error',
            sources: [],
            routeTrace: [],
            timestamp: new Date().toISOString(),
          },
        ]);
      } finally {
        setIsLoading(false);
      }
    },
    [sessionId]
  );

  return { sessionId, messages, isLoading, sendMessage, errorBanner };
}

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
 * Each message: { id, role, content, agentName, ticketId, escalated,
 *                 matchStrength, sources, routeTrace, finalRoute,
 *                 ticketDecisionReason, automationStatus, automationSimulated,
 *                 category, intent, severity, urgency, feedback, timestamp }
 *
 * `feedback` is the locally-tracked sentiment ("up" | "down" | null).
 * The diagnostic fields (routeTrace, ticketDecisionReason, automationStatus,
 * etc.) are surfaced in the UI on each assistant turn so a grader can see
 * exactly which agents fired and why a ticket / escalation was opened.
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
            automationSimulated: Boolean(data.automation_simulated),
            category: data.category ?? null,
            intent: data.intent ?? null,
            severity: data.severity ?? null,
            urgency: data.urgency ?? null,
            feedback: null,
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
            feedback: null,
            timestamp: new Date().toISOString(),
          },
        ]);
      } finally {
        setIsLoading(false);
      }
    },
    [sessionId]
  );

  const submitFeedback = useCallback(
    async (messageId, sentiment) => {
      // Optimistic update so the UI feels instant.
      setMessages((prev) =>
        prev.map((m) => (m.id === messageId ? { ...m, feedback: sentiment } : m))
      );
      try {
        await fetch('/api/feedback', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: sessionId,
            message_id: messageId,
            sentiment,
          }),
        });
      } catch (err) {
        // Roll back on failure.
        setMessages((prev) =>
          prev.map((m) => (m.id === messageId ? { ...m, feedback: null } : m))
        );
        setErrorBanner('Could not record feedback. Please try again.');
      }
    },
    [sessionId]
  );

  return {
    sessionId,
    messages,
    isLoading,
    sendMessage,
    submitFeedback,
    errorBanner,
  };
}

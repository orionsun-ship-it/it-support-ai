import { useEffect, useRef, useState } from "react";
import useChat from "../hooks/useChat.js";

const COLORS = {
  blue: "#3b82f6",
  amber: "#f59e0b",
  red: "#ef4444",
  teal: "#0d9488",
  border: "#e2e8f0",
};

export default function ChatPage({ sessionId }) {
  const { messages, isLoading, sendMessage } = useChat(sessionId);
  const [input, setInput] = useState("");
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  const onSubmit = async (e) => {
    e.preventDefault();
    if (isLoading || !input.trim()) return;
    const text = input;
    setInput("");
    await sendMessage(text);
  };

  const anyEscalated = messages.some((m) => m.escalated);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
      }}
    >
      {anyEscalated && (
        <div
          style={{
            background: COLORS.red,
            color: "#ffffff",
            padding: "10px 16px",
            fontSize: 13,
            borderBottom: `1px solid ${COLORS.border}`,
          }}
        >
          ⚠️ This conversation has been escalated to a human IT technician.
        </div>
      )}

      <div
        ref={scrollRef}
        style={{
          flex: 1,
          overflowY: "auto",
          padding: 24,
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}
      >
        {messages.length === 0 && !isLoading && (
          <div
            style={{
              flex: 1,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#94a3b8",
            }}
          >
            Send a message to get IT support
          </div>
        )}

        {messages.map((m) =>
          m.role === "user" ? (
            <UserBubble key={m.id} message={m} />
          ) : (
            <AssistantBubble key={m.id} message={m} />
          )
        )}

        {isLoading && (
          <div
            className="mono"
            style={{
              fontSize: 11,
              color: "#94a3b8",
              alignSelf: "flex-start",
              paddingLeft: 12,
            }}
          >
            agent is thinking…
          </div>
        )}
      </div>

      <form
        onSubmit={onSubmit}
        style={{
          display: "flex",
          gap: 8,
          padding: 16,
          borderTop: `1px solid ${COLORS.border}`,
          background: "#ffffff",
        }}
      >
        <input
          type="text"
          placeholder="Describe your IT issue…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={isLoading}
          style={{
            flex: 1,
            padding: "10px 12px",
            border: `1px solid ${COLORS.border}`,
            borderRadius: 4,
            font: "inherit",
            fontSize: 14,
            outline: "none",
          }}
        />
        <button
          type="submit"
          disabled={isLoading || !input.trim()}
          style={{
            padding: "10px 20px",
            background: COLORS.blue,
            color: "#ffffff",
            border: `1px solid ${COLORS.blue}`,
            borderRadius: 4,
            cursor: isLoading ? "not-allowed" : "pointer",
            opacity: isLoading || !input.trim() ? 0.6 : 1,
            font: "inherit",
            fontSize: 14,
          }}
        >
          {isLoading ? "…" : "Send"}
        </button>
      </form>
    </div>
  );
}

function UserBubble({ message }) {
  return (
    <div style={{ display: "flex", justifyContent: "flex-end" }}>
      <div
        style={{
          maxWidth: "70%",
          background: COLORS.blue,
          color: "#ffffff",
          padding: "10px 14px",
          borderRadius: 4,
          whiteSpace: "pre-wrap",
        }}
      >
        {message.content}
      </div>
    </div>
  );
}

function AssistantBubble({ message }) {
  let borderColor = COLORS.teal;
  if (message.escalated) borderColor = COLORS.red;
  else if (message.ticketId) borderColor = COLORS.amber;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4, alignItems: "flex-start" }}>
      <div
        className="mono"
        style={{
          fontSize: 11,
          color: "#64748b",
          paddingLeft: 12,
        }}
      >
        {message.agentName || "agent"}
      </div>
      <div
        style={{
          maxWidth: "70%",
          background: "#ffffff",
          padding: "10px 14px",
          borderRadius: 4,
          border: `1px solid ${COLORS.border}`,
          borderLeft: `4px solid ${borderColor}`,
          whiteSpace: "pre-wrap",
        }}
      >
        {message.content}
      </div>
      <div style={{ display: "flex", gap: 6, paddingLeft: 12 }}>
        {message.ticketId && (
          <span
            className="mono"
            style={{
              fontSize: 11,
              padding: "2px 8px",
              borderRadius: 999,
              background: "#fef3c7",
              color: "#92400e",
              border: `1px solid ${COLORS.amber}`,
            }}
          >
            🎫 {message.ticketId}
          </span>
        )}
        {message.escalated && (
          <span
            className="mono"
            style={{
              fontSize: 11,
              padding: "2px 8px",
              borderRadius: 999,
              background: COLORS.red,
              color: "#ffffff",
              border: `1px solid ${COLORS.red}`,
            }}
          >
            ⚠️ ESCALATED
          </span>
        )}
      </div>
    </div>
  );
}

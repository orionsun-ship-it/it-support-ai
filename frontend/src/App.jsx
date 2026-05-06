import { useMemo, useState } from "react";
import ChatPage from "./pages/ChatPage.jsx";
import TicketsPage from "./pages/TicketsPage.jsx";
import MetricsPage from "./pages/MetricsPage.jsx";

const COLORS = {
  sidebarBg: "#0f172a",
  mainBg: "#f8fafc",
  blue: "#3b82f6",
  border: "#e2e8f0",
};

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

const NAV_ITEMS = [
  { id: "chat", label: "Chat" },
  { id: "tickets", label: "Tickets" },
  { id: "metrics", label: "Metrics" },
];

export default function App() {
  const [activePage, setActivePage] = useState("chat");
  const [sessionId, setSessionId] = useState(() => uuid());

  const truncatedSession = useMemo(
    () => sessionId.slice(0, 12) + "...",
    [sessionId]
  );

  const onNewSession = () => setSessionId(uuid());

  return (
    <div style={{ display: "flex", height: "100vh", background: COLORS.mainBg }}>
      <aside
        style={{
          width: 220,
          flexShrink: 0,
          background: COLORS.sidebarBg,
          color: "#e2e8f0",
          padding: "20px 16px",
          display: "flex",
          flexDirection: "column",
          gap: 16,
          borderRight: `1px solid ${COLORS.border}`,
        }}
      >
        <div
          className="mono"
          style={{ fontSize: 16, fontWeight: 600, letterSpacing: 0.5 }}
        >
          IT Support AI
        </div>

        <nav style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {NAV_ITEMS.map((item) => {
            const isActive = activePage === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActivePage(item.id)}
                style={{
                  textAlign: "left",
                  padding: "8px 12px",
                  background: isActive ? "#1e293b" : "transparent",
                  color: isActive ? "#ffffff" : "#cbd5e1",
                  border: `1px solid ${isActive ? "#334155" : "transparent"}`,
                  borderRadius: 4,
                  cursor: "pointer",
                  font: "inherit",
                  fontSize: 14,
                }}
              >
                {item.label}
              </button>
            );
          })}
        </nav>

        <div style={{ flex: 1 }} />

        <div
          style={{
            borderTop: "1px solid #1e293b",
            paddingTop: 12,
            display: "flex",
            flexDirection: "column",
            gap: 8,
          }}
        >
          <div style={{ fontSize: 11, color: "#64748b" }}>SESSION</div>
          <div className="mono" style={{ fontSize: 12, color: "#cbd5e1" }}>
            {truncatedSession}
          </div>
          <button
            onClick={onNewSession}
            style={{
              padding: "6px 10px",
              background: COLORS.blue,
              color: "#ffffff",
              border: "1px solid " + COLORS.blue,
              borderRadius: 4,
              cursor: "pointer",
              font: "inherit",
              fontSize: 12,
            }}
          >
            New Session
          </button>
        </div>
      </aside>

      <main
        style={{
          flex: 1,
          minWidth: 0,
          overflow: "auto",
          background: COLORS.mainBg,
        }}
      >
        {activePage === "chat" && (
          <ChatPage sessionId={sessionId} onNewSession={onNewSession} />
        )}
        {activePage === "tickets" && <TicketsPage />}
        {activePage === "metrics" && <MetricsPage />}
      </main>
    </div>
  );
}

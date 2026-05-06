import { useEffect, useMemo, useState } from "react";
import ChatPage from "./pages/ChatPage.jsx";
import TicketsPage from "./pages/TicketsPage.jsx";
import MetricsPage from "./pages/MetricsPage.jsx";
import SourcesPage from "./pages/SourcesPage.jsx";

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

const NAV = [
  { id: "chat", label: "Chat", icon: ChatIcon },
  { id: "tickets", label: "Tickets", icon: TicketIcon },
  { id: "metrics", label: "Metrics", icon: MetricsIcon },
  { id: "sources", label: "Sources", icon: SourcesIcon },
];

export default function App() {
  const [activePage, setActivePage] = useState("chat");
  const [sessionId, setSessionId] = useState(() => uuid());
  const [opsHealth, setOpsHealth] = useState({ ok: true, kbSeeded: true });

  useEffect(() => {
    let cancelled = false;
    async function probe() {
      try {
        const resp = await fetch("/api/health");
        if (!resp.ok) throw new Error();
        const data = await resp.json();
        if (!cancelled)
          setOpsHealth({
            ok: Boolean(data.ops_api_available),
            kbSeeded: Boolean(data.kb_seeded),
          });
      } catch {
        if (!cancelled) setOpsHealth({ ok: false, kbSeeded: false });
      }
    }
    probe();
    const id = setInterval(probe, 30000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const truncatedSession = useMemo(
    () => sessionId.slice(0, 8) + "…" + sessionId.slice(-4),
    [sessionId]
  );

  return (
    <div style={{ display: "flex", height: "100vh", background: "var(--bg)" }}>
      <Sidebar
        activePage={activePage}
        setActivePage={setActivePage}
        sessionId={truncatedSession}
        onNewSession={() => setSessionId(uuid())}
        opsHealth={opsHealth}
      />
      <main
        style={{
          flex: 1,
          minWidth: 0,
          overflow: "auto",
          background: "var(--bg)",
        }}
      >
        {activePage === "chat" && (
          <ChatPage key={sessionId} sessionId={sessionId} />
        )}
        {activePage === "tickets" && <TicketsPage />}
        {activePage === "metrics" && <MetricsPage />}
        {activePage === "sources" && <SourcesPage />}
      </main>
    </div>
  );
}

function Sidebar({ activePage, setActivePage, sessionId, onNewSession, opsHealth }) {
  return (
    <aside
      style={{
        width: 248,
        flexShrink: 0,
        background:
          "linear-gradient(180deg, var(--sidebar-bg) 0%, var(--sidebar-bg-2) 100%)",
        color: "var(--sidebar-text)",
        padding: "24px 16px 20px",
        display: "flex",
        flexDirection: "column",
        gap: 28,
        borderRight: "1px solid rgba(255,255,255,0.06)",
      }}
    >
      <Brand />

      <nav style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        <SectionLabel>Workspace</SectionLabel>
        {NAV.map((item) => {
          const Active = activePage === item.id;
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              onClick={() => setActivePage(item.id)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                textAlign: "left",
                padding: "9px 12px",
                background: Active ? "var(--sidebar-active)" : "transparent",
                color: Active ? "var(--sidebar-text-strong)" : "var(--sidebar-text)",
                border: `1px solid ${
                  Active ? "var(--sidebar-active-border)" : "transparent"
                }`,
                borderRadius: 8,
                font: "inherit",
                fontSize: 13.5,
                fontWeight: Active ? 600 : 500,
                transition: "background 120ms ease, color 120ms ease",
              }}
              onMouseOver={(e) => {
                if (!Active) e.currentTarget.style.background = "rgba(255,255,255,0.04)";
              }}
              onMouseOut={(e) => {
                if (!Active) e.currentTarget.style.background = "transparent";
              }}
            >
              <Icon size={16} color={Active ? "#93c5fd" : "#94a3b8"} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      <div style={{ flex: 1 }} />

      <div
        style={{
          borderTop: "1px solid rgba(255,255,255,0.06)",
          paddingTop: 16,
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}
      >
        <StatusPill ok={opsHealth.ok} kbSeeded={opsHealth.kbSeeded} />

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 6,
            background: "rgba(255,255,255,0.03)",
            padding: "10px 12px",
            borderRadius: 8,
            border: "1px solid rgba(255,255,255,0.05)",
          }}
        >
          <div
            style={{
              fontSize: 10.5,
              fontWeight: 600,
              color: "var(--sidebar-text-muted)",
              letterSpacing: 0.6,
              textTransform: "uppercase",
            }}
          >
            Session
          </div>
          <div
            className="mono"
            style={{ fontSize: 12, color: "var(--sidebar-text-strong)" }}
          >
            {sessionId}
          </div>
          <button
            onClick={onNewSession}
            style={{
              marginTop: 4,
              padding: "7px 10px",
              background: "rgba(255,255,255,0.06)",
              color: "var(--sidebar-text-strong)",
              border: "1px solid rgba(255,255,255,0.1)",
              borderRadius: 6,
              font: "inherit",
              fontSize: 12,
              fontWeight: 500,
            }}
            onMouseOver={(e) =>
              (e.currentTarget.style.background = "rgba(255,255,255,0.1)")
            }
            onMouseOut={(e) =>
              (e.currentTarget.style.background = "rgba(255,255,255,0.06)")
            }
          >
            New session
          </button>
        </div>
      </div>
    </aside>
  );
}

function Brand() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, paddingLeft: 4 }}>
      <div
        style={{
          width: 28,
          height: 28,
          borderRadius: 8,
          background: "linear-gradient(135deg, #3b82f6 0%, #0d9488 100%)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          boxShadow: "inset 0 0 0 1px rgba(255,255,255,0.15)",
        }}
      >
        <SparkIcon size={16} color="#fff" />
      </div>
      <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.15 }}>
        <span
          style={{
            fontSize: 14,
            fontWeight: 600,
            color: "var(--sidebar-text-strong)",
            letterSpacing: 0.1,
          }}
        >
          IT Support
        </span>
        <span
          className="mono"
          style={{ fontSize: 10.5, color: "var(--sidebar-text-muted)" }}
        >
          AI assistant
        </span>
      </div>
    </div>
  );
}

function SectionLabel({ children }) {
  return (
    <div
      style={{
        fontSize: 10.5,
        fontWeight: 600,
        color: "var(--sidebar-text-muted)",
        letterSpacing: 0.6,
        textTransform: "uppercase",
        padding: "0 12px 8px",
      }}
    >
      {children}
    </div>
  );
}

function StatusPill({ ok, kbSeeded }) {
  const color = ok && kbSeeded ? "#22c55e" : ok ? "#f59e0b" : "#ef4444";
  const label = ok && kbSeeded
    ? "All systems normal"
    : ok
    ? "KB not seeded"
    : "Ops API offline";
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "8px 12px",
        background: "rgba(255,255,255,0.03)",
        border: "1px solid rgba(255,255,255,0.05)",
        borderRadius: 8,
        fontSize: 12,
      }}
    >
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: color,
          boxShadow: `0 0 0 3px ${color}33`,
        }}
      />
      <span style={{ color: "var(--sidebar-text)" }}>{label}</span>
    </div>
  );
}

function SparkIcon({ size = 16, color = "currentColor" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path
        d="M12 3l1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7L12 3z"
        stroke={color}
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
    </svg>
  );
}
function ChatIcon({ size = 16, color = "currentColor" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path
        d="M21 12a8 8 0 1 1-3.4-6.55L21 4v5h-5"
        stroke={color}
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0"
      />
      <path
        d="M4 6.5A2.5 2.5 0 0 1 6.5 4h11A2.5 2.5 0 0 1 20 6.5v8a2.5 2.5 0 0 1-2.5 2.5H10l-4 3v-3H6.5A2.5 2.5 0 0 1 4 14.5v-8z"
        stroke={color}
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
    </svg>
  );
}
function TicketIcon({ size = 16, color = "currentColor" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path
        d="M4 8a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v2a2 2 0 0 0 0 4v2a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-2a2 2 0 0 0 0-4V8z"
        stroke={color}
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path d="M14 6v12" stroke={color} strokeWidth="1.6" strokeDasharray="2 2" />
    </svg>
  );
}
function MetricsIcon({ size = 16, color = "currentColor" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path
        d="M4 19V5M9 19v-8M14 19v-5M19 19v-11"
        stroke={color}
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}
function SourcesIcon({ size = 16, color = "currentColor" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path
        d="M5 4h11l3 3v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1z"
        stroke={color}
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path d="M16 4v3h3M8 12h8M8 16h8M8 8h3" stroke={color} strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

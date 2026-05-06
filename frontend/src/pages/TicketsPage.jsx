import { useEffect, useState } from "react";

export default function TicketsPage() {
  const [tickets, setTickets] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch("/api/tickets");
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setTickets(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err.message || String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  return (
    <div style={{ padding: "32px 32px 40px", maxWidth: 1180, margin: "0 auto" }}>
      <PageHeader
        title="Tickets"
        subtitle="All issues opened by the assistant or filed manually."
        right={
          <RefreshButton onClick={refresh} loading={loading} />
        }
      />

      <div
        style={{
          marginTop: 24,
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-lg)",
          boxShadow: "var(--shadow-xs)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            padding: "14px 20px",
            borderBottom: "1px solid var(--border)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            background: "var(--surface-soft)",
          }}
        >
          <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>
            <span style={{ fontWeight: 600, color: "var(--text)" }}>
              {tickets.length}
            </span>{" "}
            ticket{tickets.length === 1 ? "" : "s"}
          </div>
        </div>

        {error && (
          <div
            style={{
              padding: "20px",
              color: "#991b1b",
              background: "var(--red-soft)",
              borderBottom: "1px solid #fca5a5",
              fontSize: 13,
            }}
          >
            Failed to load tickets: {error}
          </div>
        )}

        {tickets.length === 0 && !loading && !error ? (
          <EmptyState />
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ background: "var(--surface-soft)" }}>
                  <Th>Ticket ID</Th>
                  <Th>Title</Th>
                  <Th>Category</Th>
                  <Th>Priority</Th>
                  <Th>Status</Th>
                  <Th>Created</Th>
                </tr>
              </thead>
              <tbody>
                {tickets.map((t, idx) => (
                  <tr
                    key={t.ticket_id}
                    style={{
                      borderTop: "1px solid var(--border)",
                      background: idx % 2 === 0 ? "transparent" : "var(--surface-soft)",
                    }}
                    onMouseOver={(e) =>
                      (e.currentTarget.style.background = "#f0f6ff")
                    }
                    onMouseOut={(e) =>
                      (e.currentTarget.style.background =
                        idx % 2 === 0 ? "transparent" : "var(--surface-soft)")
                    }
                  >
                    <Td>
                      <span
                        className="mono"
                        style={{
                          background: "#f1f5f9",
                          padding: "2px 7px",
                          borderRadius: 5,
                          fontSize: 12,
                          color: "#0f172a",
                        }}
                      >
                        {t.ticket_id}
                      </span>
                    </Td>
                    <Td>
                      <span style={{ color: "var(--text)" }}>{t.title}</span>
                    </Td>
                    <Td>
                      <span style={{ color: "var(--text-secondary)" }}>
                        {t.category}
                      </span>
                    </Td>
                    <Td>
                      <PriorityChip priority={t.priority} />
                    </Td>
                    <Td>
                      <StatusChip status={t.status} />
                    </Td>
                    <Td>
                      <span
                        className="mono"
                        style={{ fontSize: 11.5, color: "var(--text-muted)" }}
                      >
                        {formatDate(t.created_at)}
                      </span>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function PageHeader({ title, subtitle, right }) {
  return (
    <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between" }}>
      <div>
        <h2
          style={{
            margin: 0,
            fontSize: 22,
            fontWeight: 600,
            color: "var(--text)",
            letterSpacing: -0.3,
          }}
        >
          {title}
        </h2>
        <div style={{ marginTop: 4, color: "var(--text-muted)", fontSize: 13.5 }}>
          {subtitle}
        </div>
      </div>
      {right}
    </div>
  );
}

function RefreshButton({ onClick, loading }) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      style={{
        padding: "8px 14px",
        background: "var(--surface)",
        color: "var(--text)",
        border: "1px solid var(--border-strong)",
        borderRadius: 8,
        fontSize: 13,
        fontWeight: 500,
        boxShadow: "var(--shadow-xs)",
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
      }}
    >
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
        <path
          d="M4 4v6h6M20 20v-6h-6M5 14a8 8 0 0 0 14 4M19 10a8 8 0 0 0-14-4"
          stroke="currentColor"
          strokeWidth="1.7"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      {loading ? "Refreshing…" : "Refresh"}
    </button>
  );
}

function EmptyState() {
  return (
    <div
      style={{
        padding: "56px 24px",
        textAlign: "center",
        color: "var(--text-muted)",
      }}
    >
      <div
        style={{
          width: 48,
          height: 48,
          borderRadius: 12,
          background: "var(--brand-soft)",
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          marginBottom: 14,
        }}
      >
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
          <path
            d="M4 8a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v2a2 2 0 0 0 0 4v2a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-2a2 2 0 0 0 0-4V8z"
            stroke="#2563eb"
            strokeWidth="1.7"
            strokeLinejoin="round"
          />
        </svg>
      </div>
      <div style={{ color: "var(--text)", fontWeight: 500, fontSize: 14 }}>
        No tickets yet
      </div>
      <div style={{ marginTop: 4, fontSize: 13 }}>
        Start a conversation. The assistant will only open a ticket when an issue
        actually needs follow-up.
      </div>
    </div>
  );
}

function Th({ children }) {
  return (
    <th
      style={{
        textAlign: "left",
        padding: "10px 16px",
        fontWeight: 600,
        color: "var(--text-muted)",
        fontSize: 11,
        textTransform: "uppercase",
        letterSpacing: 0.6,
      }}
    >
      {children}
    </th>
  );
}

function Td({ children }) {
  return (
    <td style={{ padding: "12px 16px", verticalAlign: "middle" }}>{children}</td>
  );
}

function PriorityChip({ priority }) {
  const cfg =
    {
      low: { bg: "var(--green-soft)", color: "#065f46", border: "#6ee7b7" },
      medium: { bg: "var(--brand-soft)", color: "#1e40af", border: "#bfdbfe" },
      high: { bg: "var(--amber-soft)", color: "#92400e", border: "#fcd34d" },
      critical: { bg: "var(--red-soft)", color: "#991b1b", border: "#fca5a5" },
    }[priority] || { bg: "#f1f5f9", color: "#334155", border: "#cbd5e1" };
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "3px 9px",
        borderRadius: 6,
        background: cfg.bg,
        color: cfg.color,
        border: `1px solid ${cfg.border}`,
        fontSize: 11,
        fontWeight: 600,
        textTransform: "uppercase",
        letterSpacing: 0.4,
      }}
    >
      {priority}
    </span>
  );
}

function StatusChip({ status }) {
  if (status === "escalated") {
    return (
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 5,
          padding: "3px 9px",
          borderRadius: 999,
          background: "var(--red-soft)",
          color: "#991b1b",
          border: "1px solid #fca5a5",
          fontSize: 11.5,
          fontWeight: 500,
        }}
      >
        <DotInline color="#dc2626" /> escalated
      </span>
    );
  }
  if (status === "resolved" || status === "closed") {
    return (
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 5,
          padding: "3px 9px",
          borderRadius: 999,
          background: "var(--green-soft)",
          color: "#065f46",
          border: "1px solid #6ee7b7",
          fontSize: 11.5,
          fontWeight: 500,
        }}
      >
        <DotInline color="#059669" /> {status}
      </span>
    );
  }
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        padding: "3px 9px",
        borderRadius: 999,
        background: "var(--brand-soft)",
        color: "#1e40af",
        border: "1px solid #bfdbfe",
        fontSize: 11.5,
        fontWeight: 500,
      }}
    >
      <DotInline color="#2563eb" /> {status || "open"}
    </span>
  );
}

function DotInline({ color }) {
  return (
    <span
      style={{
        width: 6,
        height: 6,
        borderRadius: "50%",
        background: color,
        display: "inline-block",
      }}
    />
  );
}

function formatDate(value) {
  if (!value) return "";
  try {
    return new Date(value).toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return String(value);
  }
}

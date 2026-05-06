import { useEffect, useState } from "react";

const COLORS = {
  border: "#e2e8f0",
  blue: "#3b82f6",
  green: "#10b981",
  amber: "#f59e0b",
  orangeRed: "#f97316",
  red: "#ef4444",
};

const PRIORITY_BG = {
  low: COLORS.green,
  medium: COLORS.amber,
  high: COLORS.orangeRed,
  critical: COLORS.red,
};

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
    <div style={{ padding: 24 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 16,
        }}
      >
        <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>Tickets</h2>
        <button
          onClick={refresh}
          disabled={loading}
          style={{
            padding: "6px 12px",
            background: "#ffffff",
            color: "#0f172a",
            border: `1px solid ${COLORS.border}`,
            borderRadius: 4,
            cursor: loading ? "not-allowed" : "pointer",
            font: "inherit",
            fontSize: 13,
          }}
        >
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      <div style={{ marginBottom: 12, color: "#64748b", fontSize: 13 }}>
        {tickets.length} ticket{tickets.length === 1 ? "" : "s"}
      </div>

      {error && (
        <div
          style={{
            background: "#fee2e2",
            color: "#991b1b",
            padding: 12,
            borderRadius: 4,
            border: `1px solid ${COLORS.red}`,
            marginBottom: 16,
          }}
        >
          Failed to load tickets: {error}
        </div>
      )}

      {tickets.length === 0 && !loading && !error ? (
        <div
          style={{
            padding: 32,
            textAlign: "center",
            color: "#94a3b8",
            border: `1px dashed ${COLORS.border}`,
            borderRadius: 4,
          }}
        >
          No tickets yet. Start a conversation to generate tickets.
        </div>
      ) : (
        <div
          style={{
            background: "#ffffff",
            border: `1px solid ${COLORS.border}`,
            borderRadius: 4,
            overflow: "hidden",
          }}
        >
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ background: "#f1f5f9" }}>
                <Th>Ticket ID</Th>
                <Th>Title</Th>
                <Th>Category</Th>
                <Th>Priority</Th>
                <Th>Status</Th>
                <Th>Created At</Th>
              </tr>
            </thead>
            <tbody>
              {tickets.map((t) => (
                <tr
                  key={t.ticket_id}
                  style={{ borderTop: `1px solid ${COLORS.border}` }}
                >
                  <Td>
                    <span className="mono">{t.ticket_id}</span>
                  </Td>
                  <Td>{t.title}</Td>
                  <Td>{t.category}</Td>
                  <Td>
                    <PriorityBadge priority={t.priority} />
                  </Td>
                  <Td>
                    <StatusBadge status={t.status} />
                  </Td>
                  <Td>
                    <span className="mono" style={{ fontSize: 12 }}>
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
  );
}

function Th({ children }) {
  return (
    <th
      style={{
        textAlign: "left",
        padding: "10px 12px",
        fontWeight: 600,
        color: "#475569",
        fontSize: 12,
        textTransform: "uppercase",
        letterSpacing: 0.5,
      }}
    >
      {children}
    </th>
  );
}

function Td({ children }) {
  return <td style={{ padding: "10px 12px", verticalAlign: "middle" }}>{children}</td>;
}

function PriorityBadge({ priority }) {
  const bg = PRIORITY_BG[priority] || "#cbd5e1";
  const isCritical = priority === "critical";
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 8px",
        borderRadius: 4,
        background: bg,
        color: isCritical ? "#ffffff" : "#0f172a",
        fontSize: 11,
        fontWeight: 500,
        textTransform: "uppercase",
        letterSpacing: 0.5,
      }}
    >
      {priority}
    </span>
  );
}

function StatusBadge({ status }) {
  if (status === "escalated") {
    return (
      <span
        style={{
          display: "inline-block",
          padding: "2px 8px",
          borderRadius: 4,
          background: COLORS.red,
          color: "#ffffff",
          fontSize: 11,
          fontWeight: 500,
        }}
      >
        escalated
      </span>
    );
  }
  if (status === "resolved") {
    return (
      <span
        style={{
          display: "inline-block",
          padding: "2px 8px",
          borderRadius: 4,
          background: COLORS.green,
          color: "#ffffff",
          fontSize: 11,
          fontWeight: 500,
        }}
      >
        resolved
      </span>
    );
  }
  // open or unknown
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 8px",
        borderRadius: 4,
        background: "#ffffff",
        color: COLORS.blue,
        border: `1px solid ${COLORS.blue}`,
        fontSize: 11,
        fontWeight: 500,
      }}
    >
      {status || "open"}
    </span>
  );
}

function formatDate(value) {
  if (!value) return "";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return String(value);
  }
}

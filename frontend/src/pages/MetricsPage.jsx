import { useEffect, useState } from "react";

const COLORS = {
  border: "#e2e8f0",
  blue: "#3b82f6",
  green: "#10b981",
  amber: "#f59e0b",
  red: "#ef4444",
  gray: "#64748b",
};

export default function MetricsPage() {
  const [metrics, setMetrics] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch("/api/metrics");
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      setMetrics(await resp.json());
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
        <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>System Metrics</h2>
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
          Failed to load metrics: {error}
        </div>
      )}

      {metrics && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
            gap: 12,
          }}
        >
          <Card label="Total Requests" value={metrics.total_requests} accent={COLORS.blue} />
          <Card
            label="Avg Response Time"
            value={`${(metrics.avg_response_time_ms || 0).toFixed(1)}ms`}
            accent={metrics.avg_response_time_ms > 3000 ? COLORS.amber : COLORS.green}
          />
          <Card label="Total Tickets" value={metrics.total_tickets} accent={COLORS.blue} />
          <Card
            label="Total Escalations"
            value={metrics.total_escalations}
            accent={metrics.total_escalations > 0 ? COLORS.red : COLORS.gray}
          />
          <Card
            label="Knowledge Base"
            value={metrics.kb_seeded ? "Seeded" : "Not Seeded"}
            accent={metrics.kb_seeded ? COLORS.green : COLORS.red}
          />
          <Card
            label="System Uptime"
            value={formatUptime(metrics.uptime_seconds)}
            accent={COLORS.gray}
          />
        </div>
      )}
    </div>
  );
}

function Card({ label, value, accent }) {
  return (
    <div
      style={{
        background: "#ffffff",
        border: `1px solid ${COLORS.border}`,
        borderTop: `3px solid ${accent}`,
        borderRadius: 4,
        padding: 16,
        display: "flex",
        flexDirection: "column",
        gap: 6,
      }}
    >
      <div
        style={{
          fontSize: 11,
          color: "#64748b",
          textTransform: "uppercase",
          letterSpacing: 0.5,
        }}
      >
        {label}
      </div>
      <div className="mono" style={{ fontSize: 22, fontWeight: 600, color: "#0f172a" }}>
        {value}
      </div>
    </div>
  );
}

function formatUptime(totalSeconds) {
  const s = Math.floor(totalSeconds || 0);
  const hours = Math.floor(s / 3600);
  const minutes = Math.floor((s % 3600) / 60);
  const seconds = s % 60;
  return `${hours}h ${minutes}m ${seconds}s`;
}

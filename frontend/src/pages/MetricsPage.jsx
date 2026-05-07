import { useEffect, useState } from 'react';

export default function MetricsPage() {
  const [metrics, setMetrics] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch('/api/metrics');
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
    <div style={{ padding: '32px 32px 40px', maxWidth: 1180, margin: '0 auto' }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-end',
          justifyContent: 'space-between',
        }}
      >
        <div>
          <h2
            style={{
              margin: 0,
              fontSize: 22,
              fontWeight: 600,
              color: 'var(--text)',
              letterSpacing: -0.3,
            }}
          >
            System metrics
          </h2>
          <div style={{ marginTop: 4, color: 'var(--text-muted)', fontSize: 13.5 }}>
            Live snapshot of the assistant pipeline and dependencies.
          </div>
        </div>

        <button
          onClick={refresh}
          disabled={loading}
          style={{
            padding: '8px 14px',
            background: 'var(--surface)',
            color: 'var(--text)',
            border: '1px solid var(--border-strong)',
            borderRadius: 8,
            fontSize: 13,
            fontWeight: 500,
            boxShadow: 'var(--shadow-xs)',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
          }}
        >
          {loading ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {error && (
        <div
          style={{
            marginTop: 20,
            background: 'var(--red-soft)',
            color: '#991b1b',
            padding: 16,
            borderRadius: 'var(--radius-md)',
            border: '1px solid #fca5a5',
            fontSize: 13,
          }}
        >
          Failed to load metrics: {error}
        </div>
      )}

      {metrics && (
        <div
          style={{
            marginTop: 24,
            display: 'grid',
            gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
            gap: 14,
          }}
        >
          <Card
            label="Total requests"
            value={metrics.total_requests}
            accent="brand"
            icon={<ChatGlyph />}
          />
          <Card
            label="Avg response time"
            value={`${(metrics.avg_response_time_ms || 0).toFixed(0)} ms`}
            accent={metrics.avg_response_time_ms > 3000 ? 'amber' : 'teal'}
            icon={<ClockGlyph />}
            sub={metrics.avg_response_time_ms > 3000 ? 'Above 3s target' : 'Within target'}
          />
          <Card
            label="Total tickets"
            value={metrics.total_tickets}
            accent="brand"
            icon={<TicketGlyph />}
          />
          <Card
            label="Escalations"
            value={metrics.total_escalations}
            accent={metrics.total_escalations > 0 ? 'red' : 'neutral'}
            icon={<AlertGlyph />}
            sub={metrics.total_escalations > 0 ? 'Active human handoffs' : 'No escalations'}
          />
          <Card
            label="Knowledge base"
            value={metrics.kb_seeded ? 'Seeded' : 'Not seeded'}
            accent={metrics.kb_seeded ? 'green' : 'red'}
            icon={<DbGlyph />}
            sub={metrics.kb_seeded ? 'Ready for retrieval' : 'Run make ingest'}
          />
          <Card
            label="System uptime"
            value={formatUptime(metrics.uptime_seconds)}
            accent="neutral"
            icon={<HeartGlyph />}
            sub={metrics.ops_api_available ? 'Ops API healthy' : 'Ops API unreachable'}
          />
          <Card
            label="User satisfaction"
            value={
              (metrics.feedback_total || 0) === 0
                ? '—'
                : `${Math.round((metrics.satisfaction_score || 0) * 100)}%`
            }
            accent={
              (metrics.feedback_total || 0) === 0
                ? 'neutral'
                : (metrics.satisfaction_score || 0) >= 0.7
                  ? 'green'
                  : (metrics.satisfaction_score || 0) >= 0.4
                    ? 'amber'
                    : 'red'
            }
            icon={<ThumbGlyph />}
            sub={
              (metrics.feedback_total || 0) === 0
                ? 'No feedback yet'
                : `${metrics.feedback_up || 0} up · ${metrics.feedback_down || 0} down`
            }
          />
        </div>
      )}
    </div>
  );
}

function Card({ label, value, accent = 'brand', icon, sub }) {
  const accents = {
    brand: { bar: 'var(--brand)', iconBg: 'var(--brand-soft)', iconColor: '#2563eb' },
    teal: { bar: 'var(--teal)', iconBg: 'var(--teal-soft)', iconColor: '#0f766e' },
    amber: { bar: 'var(--amber)', iconBg: 'var(--amber-soft)', iconColor: '#b45309' },
    red: { bar: 'var(--red)', iconBg: 'var(--red-soft)', iconColor: '#b91c1c' },
    green: { bar: 'var(--green)', iconBg: 'var(--green-soft)', iconColor: '#047857' },
    neutral: { bar: '#94a3b8', iconBg: '#f1f5f9', iconColor: '#475569' },
  }[accent];

  return (
    <div
      style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-lg)',
        padding: '18px 20px',
        boxShadow: 'var(--shadow-xs)',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: 3,
          background: accents.bar,
          opacity: 0.85,
        }}
      />
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div
          style={{
            fontSize: 11.5,
            fontWeight: 600,
            color: 'var(--text-muted)',
            letterSpacing: 0.6,
            textTransform: 'uppercase',
          }}
        >
          {label}
        </div>
        <div
          style={{
            width: 28,
            height: 28,
            borderRadius: 8,
            background: accents.iconBg,
            color: accents.iconColor,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {icon}
        </div>
      </div>

      <div
        className="mono"
        style={{
          fontSize: 26,
          fontWeight: 600,
          color: 'var(--text)',
          letterSpacing: -0.3,
        }}
      >
        {value}
      </div>

      {sub && <div style={{ fontSize: 12.5, color: 'var(--text-muted)' }}>{sub}</div>}
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

function ChatGlyph() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <path
        d="M4 6.5A2.5 2.5 0 0 1 6.5 4h11A2.5 2.5 0 0 1 20 6.5v8a2.5 2.5 0 0 1-2.5 2.5H10l-4 3v-3H6.5A2.5 2.5 0 0 1 4 14.5v-8z"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinejoin="round"
      />
    </svg>
  );
}
function ClockGlyph() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="8.5" stroke="currentColor" strokeWidth="1.6" />
      <path d="M12 7v5l3 2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}
function TicketGlyph() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <path
        d="M4 8a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v2a2 2 0 0 0 0 4v2a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-2a2 2 0 0 0 0-4V8z"
        stroke="currentColor"
        strokeWidth="1.6"
      />
    </svg>
  );
}
function AlertGlyph() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <path
        d="M12 4l9 16H3l9-16zM12 10v5M12 18v.01"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
function DbGlyph() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <ellipse cx="12" cy="6" rx="7" ry="2.5" stroke="currentColor" strokeWidth="1.6" />
      <path d="M5 6v12c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5V6" stroke="currentColor" strokeWidth="1.6" />
      <path d="M5 12c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  );
}
function HeartGlyph() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <path
        d="M12 20s-7-4.5-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.5-7 10-7 10z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
    </svg>
  );
}
function ThumbGlyph() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <path
        d="M7 11v9H4v-9h3zM7 11l4-7c1.5 0 2 1 2 2v4h5a2 2 0 0 1 2 2.3l-1 5a2 2 0 0 1-2 1.7H7"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
    </svg>
  );
}

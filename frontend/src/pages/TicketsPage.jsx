import { useEffect, useState } from 'react';

const STATUSES = ['open', 'in_progress', 'escalated', 'resolved'];

export default function TicketsPage() {
  const [tickets, setTickets] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [openId, setOpenId] = useState(null);
  const [updatingId, setUpdatingId] = useState(null);
  const [deletingId, setDeletingId] = useState(null);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch('/api/tickets');
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setTickets(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err.message || String(err));
    } finally {
      setLoading(false);
    }
  };

  const deleteTicket = async (ticketId) => {
    setDeletingId(ticketId);
    try {
      const resp = await fetch(`/api/tickets/${ticketId}`, { method: 'DELETE' });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      setTickets((prev) => prev.filter((t) => t.ticket_id !== ticketId));
      if (openId === ticketId) setOpenId(null);
    } catch (err) {
      setError(`Delete failed: ${err.message || String(err)}`);
    } finally {
      setDeletingId(null);
    }
  };

  const updateStatus = async (ticketId, newStatus) => {
    setUpdatingId(ticketId);
    try {
      const resp = await fetch(`/api/tickets/${ticketId}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ new_status: newStatus }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const updated = await resp.json();
      setTickets((prev) => prev.map((t) => (t.ticket_id === ticketId ? { ...t, ...updated } : t)));
    } catch (err) {
      setError(`Status update failed: ${err.message || String(err)}`);
    } finally {
      setUpdatingId(null);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  return (
    <div style={{ padding: '32px 32px 40px', maxWidth: 1180, margin: '0 auto' }}>
      <PageHeader
        title="Tickets"
        subtitle="All issues opened by the assistant or filed manually. Click a row to view details and change status."
        right={<RefreshButton onClick={refresh} loading={loading} />}
      />

      <div
        style={{
          marginTop: 24,
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius-lg)',
          boxShadow: 'var(--shadow-xs)',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            padding: '14px 20px',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            background: 'var(--surface-soft)',
          }}
        >
          <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
            <span style={{ fontWeight: 600, color: 'var(--text)' }}>{tickets.length}</span> ticket
            {tickets.length === 1 ? '' : 's'}
          </div>
        </div>

        {error && (
          <div
            style={{
              padding: '12px 20px',
              color: '#991b1b',
              background: 'var(--red-soft)',
              borderBottom: '1px solid #fca5a5',
              fontSize: 13,
            }}
          >
            {error}
          </div>
        )}

        {tickets.length === 0 && !loading && !error ? (
          <EmptyState />
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ background: 'var(--surface-soft)' }}>
                  <Th />
                  <Th>Ticket ID</Th>
                  <Th>Title</Th>
                  <Th>Category</Th>
                  <Th>Priority</Th>
                  <Th>Status</Th>
                  <Th>Created</Th>
                </tr>
              </thead>
              <tbody>
                {tickets.map((t, idx) => {
                  const isOpen = openId === t.ticket_id;
                  return (
                    <>
                      <tr
                        key={t.ticket_id}
                        onClick={() => setOpenId(isOpen ? null : t.ticket_id)}
                        style={{
                          borderTop: '1px solid var(--border)',
                          background: isOpen
                            ? '#f0f6ff'
                            : idx % 2 === 0
                              ? 'transparent'
                              : 'var(--surface-soft)',
                          cursor: 'pointer',
                        }}
                      >
                        <Td>
                          <Chevron open={isOpen} />
                        </Td>
                        <Td>
                          <span
                            className="mono"
                            style={{
                              background: '#f1f5f9',
                              padding: '2px 7px',
                              borderRadius: 5,
                              fontSize: 12,
                              color: '#0f172a',
                            }}
                          >
                            {t.ticket_id}
                          </span>
                        </Td>
                        <Td>
                          <span style={{ color: 'var(--text)' }}>{t.title}</span>
                        </Td>
                        <Td>
                          <span style={{ color: 'var(--text-secondary)' }}>{t.category}</span>
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
                            style={{ fontSize: 11.5, color: 'var(--text-muted)' }}
                          >
                            {formatDate(t.created_at)}
                          </span>
                        </Td>
                      </tr>
                      {isOpen && (
                        <tr key={t.ticket_id + '-detail'}>
                          <td
                            colSpan={7}
                            style={{
                              padding: '16px 20px 20px 56px',
                              background: 'var(--surface-soft)',
                              borderTop: '1px solid var(--border)',
                            }}
                          >
                            <DetailPanel
                              ticket={t}
                              updating={updatingId === t.ticket_id}
                              deleting={deletingId === t.ticket_id}
                              onUpdateStatus={(s) => updateStatus(t.ticket_id, s)}
                              onDelete={() => deleteTicket(t.ticket_id)}
                            />
                          </td>
                        </tr>
                      )}
                    </>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function DetailPanel({ ticket, updating, deleting, onUpdateStatus, onDelete }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div
        style={{
          fontSize: 11,
          fontWeight: 600,
          color: 'var(--text-muted)',
          letterSpacing: 0.6,
          textTransform: 'uppercase',
        }}
      >
        Description
      </div>
      <div
        style={{
          fontSize: 13.5,
          color: 'var(--text-secondary)',
          lineHeight: 1.6,
          whiteSpace: 'pre-wrap',
          maxWidth: 760,
        }}
      >
        {ticket.description || '(no description)'}
      </div>

      <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', fontSize: 12.5 }}>
        <Meta label="Severity" value={ticket.severity} />
        <Meta label="Urgency" value={ticket.urgency} />
        <Meta label="Session" value={ticket.session_id} mono />
        {ticket.updated_at && <Meta label="Updated" value={formatDate(ticket.updated_at)} />}
      </div>

      <div
        style={{
          marginTop: 4,
          display: 'flex',
          gap: 8,
          flexWrap: 'wrap',
          alignItems: 'center',
        }}
      >
        <span
          style={{
            fontSize: 11,
            fontWeight: 600,
            color: 'var(--text-muted)',
            letterSpacing: 0.6,
            textTransform: 'uppercase',
            marginRight: 4,
          }}
        >
          Set status
        </span>
        {STATUSES.map((s) => {
          const active = ticket.status === s;
          return (
            <button
              key={s}
              disabled={updating || active}
              onClick={(e) => {
                e.stopPropagation();
                onUpdateStatus(s);
              }}
              style={{
                padding: '5px 11px',
                fontSize: 12,
                fontWeight: 500,
                borderRadius: 6,
                cursor: active || updating ? 'not-allowed' : 'pointer',
                border: `1px solid ${active ? 'var(--brand)' : 'var(--border-strong)'}`,
                background: active ? 'var(--brand)' : 'var(--surface)',
                color: active ? '#fff' : 'var(--text)',
              }}
            >
              {s.replace('_', ' ')}
            </button>
          );
        })}
        {updating && <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>updating…</span>}
      </div>

      <div style={{ marginTop: 8, paddingTop: 12, borderTop: '1px solid var(--border)' }}>
        <button
          disabled={deleting || updating}
          onClick={(e) => {
            e.stopPropagation();
            if (window.confirm(`Delete ticket ${ticket.ticket_id}? This cannot be undone.`)) {
              onDelete();
            }
          }}
          style={{
            padding: '6px 12px',
            fontSize: 12,
            fontWeight: 500,
            borderRadius: 6,
            cursor: deleting || updating ? 'not-allowed' : 'pointer',
            border: '1px solid #fca5a5',
            background: 'var(--red-soft)',
            color: '#991b1b',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
          }}
        >
          <TrashIcon />
          {deleting ? 'Deleting…' : 'Delete ticket'}
        </button>
      </div>
    </div>
  );
}

function Meta({ label, value, mono }) {
  return (
    <div>
      <span style={{ color: 'var(--text-muted)' }}>{label}: </span>
      <span
        className={mono ? 'mono' : undefined}
        style={{ color: 'var(--text)', fontWeight: mono ? 400 : 500 }}
      >
        {value || '—'}
      </span>
    </div>
  );
}

function Chevron({ open }) {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill="none"
      style={{
        transition: 'transform 150ms ease',
        transform: open ? 'rotate(90deg)' : 'none',
        color: 'var(--text-muted)',
      }}
    >
      <path
        d="M9 6l6 6-6 6"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function PageHeader({ title, subtitle, right }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between' }}>
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
          {title}
        </h2>
        <div style={{ marginTop: 4, color: 'var(--text-muted)', fontSize: 13.5 }}>{subtitle}</div>
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
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
        <path
          d="M4 4v6h6M20 20v-6h-6M5 14a8 8 0 0 0 14 4M19 10a8 8 0 0 0-14-4"
          stroke="currentColor"
          strokeWidth="1.7"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      {loading ? 'Refreshing…' : 'Refresh'}
    </button>
  );
}

function EmptyState() {
  return (
    <div style={{ padding: '56px 24px', textAlign: 'center', color: 'var(--text-muted)' }}>
      <div
        style={{
          width: 48,
          height: 48,
          borderRadius: 12,
          background: 'var(--brand-soft)',
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
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
      <div style={{ color: 'var(--text)', fontWeight: 500, fontSize: 14 }}>No tickets yet</div>
      <div style={{ marginTop: 4, fontSize: 13 }}>
        Start a conversation. The assistant only opens a ticket when an issue actually needs
        follow-up.
      </div>
    </div>
  );
}

function Th({ children }) {
  return (
    <th
      style={{
        textAlign: 'left',
        padding: '10px 16px',
        fontWeight: 600,
        color: 'var(--text-muted)',
        fontSize: 11,
        textTransform: 'uppercase',
        letterSpacing: 0.6,
      }}
    >
      {children}
    </th>
  );
}

function Td({ children }) {
  return <td style={{ padding: '12px 16px', verticalAlign: 'middle' }}>{children}</td>;
}

function PriorityChip({ priority }) {
  const cfg = {
    low: { bg: 'var(--green-soft)', color: '#065f46', border: '#6ee7b7' },
    medium: { bg: 'var(--brand-soft)', color: '#1e40af', border: '#bfdbfe' },
    high: { bg: 'var(--amber-soft)', color: '#92400e', border: '#fcd34d' },
    critical: { bg: 'var(--red-soft)', color: '#991b1b', border: '#fca5a5' },
  }[priority] || { bg: '#f1f5f9', color: '#334155', border: '#cbd5e1' };
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '3px 9px',
        borderRadius: 6,
        background: cfg.bg,
        color: cfg.color,
        border: `1px solid ${cfg.border}`,
        fontSize: 11,
        fontWeight: 600,
        textTransform: 'uppercase',
        letterSpacing: 0.4,
      }}
    >
      {priority}
    </span>
  );
}

function StatusChip({ status }) {
  if (status === 'escalated') {
    return (
      <span style={pill('var(--red-soft)', '#991b1b', '#fca5a5')}>
        <DotInline color="#dc2626" /> escalated
      </span>
    );
  }
  if (status === 'resolved' || status === 'closed') {
    return (
      <span style={pill('var(--green-soft)', '#065f46', '#6ee7b7')}>
        <DotInline color="#059669" /> {status}
      </span>
    );
  }
  if (status === 'in_progress') {
    return (
      <span style={pill('var(--amber-soft)', '#92400e', '#fcd34d')}>
        <DotInline color="#d97706" /> in progress
      </span>
    );
  }
  return (
    <span style={pill('var(--brand-soft)', '#1e40af', '#bfdbfe')}>
      <DotInline color="#2563eb" /> {status || 'open'}
    </span>
  );
}

function pill(bg, color, border) {
  return {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 5,
    padding: '3px 9px',
    borderRadius: 999,
    background: bg,
    color,
    border: `1px solid ${border}`,
    fontSize: 11.5,
    fontWeight: 500,
  };
}

function DotInline({ color }) {
  return (
    <span
      style={{
        width: 6,
        height: 6,
        borderRadius: '50%',
        background: color,
        display: 'inline-block',
      }}
    />
  );
}

function TrashIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
      <path
        d="M3 6h18M8 6V4h8v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function formatDate(value) {
  if (!value) return '';
  try {
    return new Date(value).toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return String(value);
  }
}

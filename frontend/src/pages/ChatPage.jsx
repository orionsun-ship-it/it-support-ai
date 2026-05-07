import { useEffect, useRef, useState } from 'react';
import useChat from '../hooks/useChat.js';

export default function ChatPage({ sessionId }) {
  const { messages, isLoading, sendMessage, submitFeedback, errorBanner } = useChat(sessionId);
  const [input, setInput] = useState('');
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
    setInput('');
    await sendMessage(text);
  };

  const anyEscalated = messages.some((m) => m.escalated);

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
      }}
    >
      <Header escalated={anyEscalated} />

      {errorBanner && <Banner kind="warn" message={`Connection issue: ${errorBanner}`} />}

      <div
        ref={scrollRef}
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '32px 32px 8px',
        }}
      >
        <div
          style={{
            maxWidth: 760,
            margin: '0 auto',
            display: 'flex',
            flexDirection: 'column',
            gap: 20,
          }}
        >
          {messages.length === 0 && !isLoading && <EmptyState onPick={sendMessage} />}

          {messages.map((m) =>
            m.role === 'user' ? (
              <UserBubble key={m.id} message={m} />
            ) : (
              <AssistantBubble key={m.id} message={m} onFeedback={submitFeedback} />
            ),
          )}

          {isLoading && <ThinkingIndicator />}
        </div>
      </div>

      <Composer input={input} setInput={setInput} onSubmit={onSubmit} isLoading={isLoading} />
    </div>
  );
}

function Header({ escalated }) {
  return (
    <div
      style={{
        padding: '20px 32px',
        borderBottom: '1px solid var(--border)',
        background: 'var(--surface)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}
    >
      <div>
        <div
          style={{
            fontSize: 15,
            fontWeight: 600,
            color: 'var(--text)',
            letterSpacing: -0.1,
          }}
        >
          Support assistant
        </div>
        <div style={{ fontSize: 12.5, color: 'var(--text-muted)', marginTop: 2 }}>
          Ask about passwords, VPN, software errors, network, hardware, or access.
        </div>
      </div>
      {escalated && (
        <Chip kind="red">
          <DotIcon /> Escalated to human
        </Chip>
      )}
    </div>
  );
}

function Banner({ kind = 'warn', message }) {
  const style =
    kind === 'warn'
      ? {
          background: 'var(--amber-soft)',
          color: '#92400e',
          borderColor: '#fcd34d',
        }
      : {
          background: 'var(--red-soft)',
          color: '#991b1b',
          borderColor: '#fca5a5',
        };
  return (
    <div
      style={{
        padding: '10px 32px',
        fontSize: 12.5,
        borderBottom: `1px solid ${style.borderColor}`,
        background: style.background,
        color: style.color,
      }}
    >
      {message}
    </div>
  );
}

function EmptyState({ onPick }) {
  const samples = [
    'I forgot my password and need to reset it.',
    'How do I set up the company VPN?',
    'Outlook will not open this morning.',
    'Installer fails with error 1603.',
  ];
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 24,
        padding: '64px 16px 24px',
        textAlign: 'center',
      }}
    >
      <div
        style={{
          width: 56,
          height: 56,
          borderRadius: 14,
          background: 'linear-gradient(135deg, var(--brand-soft) 0%, var(--teal-soft) 100%)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: 'var(--shadow-sm)',
        }}
      >
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none">
          <path
            d="M12 3l1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7L12 3z"
            stroke="#2563eb"
            strokeWidth="1.6"
            strokeLinejoin="round"
          />
        </svg>
      </div>

      <div>
        <div
          style={{
            fontSize: 18,
            fontWeight: 600,
            color: 'var(--text)',
            letterSpacing: -0.2,
          }}
        >
          How can we help today?
        </div>
        <div
          style={{
            fontSize: 13.5,
            color: 'var(--text-muted)',
            marginTop: 6,
            maxWidth: 460,
          }}
        >
          Describe your IT issue in your own words. The assistant will search the knowledge base,
          run safe automations when possible, and escalate to a human when needed.
        </div>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 10,
          width: '100%',
          maxWidth: 560,
        }}
      >
        {samples.map((s) => (
          <button
            key={s}
            onClick={() => onPick(s)}
            style={{
              textAlign: 'left',
              background: 'var(--surface)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-md)',
              padding: '12px 14px',
              color: 'var(--text-secondary)',
              fontSize: 13,
              boxShadow: 'var(--shadow-xs)',
              transition: 'all 120ms ease',
            }}
            onMouseOver={(e) => {
              e.currentTarget.style.borderColor = 'var(--brand)';
              e.currentTarget.style.color = 'var(--text)';
              e.currentTarget.style.background = 'var(--brand-soft)';
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.borderColor = 'var(--border)';
              e.currentTarget.style.color = 'var(--text-secondary)';
              e.currentTarget.style.background = 'var(--surface)';
            }}
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}

function UserBubble({ message }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
      <div
        style={{
          maxWidth: '78%',
          background: 'var(--brand)',
          color: '#ffffff',
          padding: '11px 16px',
          borderRadius: '14px 14px 4px 14px',
          fontSize: 14,
          lineHeight: 1.55,
          whiteSpace: 'pre-wrap',
          boxShadow: 'var(--shadow-xs)',
        }}
      >
        {message.content}
      </div>
    </div>
  );
}

function AssistantBubble({ message, onFeedback }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Avatar />
        <span
          style={{
            fontSize: 12.5,
            color: 'var(--text-secondary)',
            fontWeight: 500,
          }}
        >
          Support assistant
        </span>
        {message.matchStrength && (
          <Chip kind={chipKindForMatch(message.matchStrength)}>
            <DotIcon />
            kb match · {message.matchStrength}
          </Chip>
        )}
      </div>

      <div
        style={{
          maxWidth: '84%',
          background: 'var(--surface)',
          padding: '14px 18px',
          borderRadius: '4px 14px 14px 14px',
          border: '1px solid var(--border)',
          fontSize: 14,
          lineHeight: 1.6,
          color: 'var(--text)',
          boxShadow: 'var(--shadow-xs)',
        }}
      >
        <MarkdownContent content={message.content} />
      </div>

      {message.sources && message.sources.length > 0 && <Sources sources={message.sources} />}

      <RouteTraceStrip message={message} />

      <div
        style={{
          display: 'flex',
          gap: 8,
          marginTop: 2,
          alignItems: 'center',
          flexWrap: 'wrap',
        }}
      >
        {message.ticketId && (
          <Chip kind="amber">
            <TicketGlyph /> <span className="mono">{message.ticketId}</span>
          </Chip>
        )}
        {message.escalated && (
          <Chip kind="red">
            <DotIcon /> Escalated
          </Chip>
        )}
        {message.automationSimulated && (
          <Chip kind="neutral">
            <DotIcon /> Simulated automation
          </Chip>
        )}
        {message.agentName !== 'error' && onFeedback && (
          <FeedbackButtons
            messageId={message.id}
            current={message.feedback}
            onFeedback={onFeedback}
          />
        )}
      </div>
    </div>
  );
}

function RouteTraceStrip({ message }) {
  const trace = Array.isArray(message.routeTrace) ? message.routeTrace : [];
  if (trace.length === 0) return null;

  const ticketReason = message.ticketDecisionReason;
  const automationStatus = message.automationStatus;

  return (
    <details
      style={{
        maxWidth: '84%',
        background: 'var(--surface-soft)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-md)',
        padding: '8px 12px',
        fontSize: 11.5,
        color: 'var(--text-secondary)',
      }}
    >
      <summary
        style={{
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          color: 'var(--text-muted)',
          fontWeight: 500,
        }}
      >
        <span
          style={{
            fontSize: 10.5,
            fontWeight: 600,
            letterSpacing: 0.6,
            textTransform: 'uppercase',
            color: 'var(--text-muted)',
          }}
        >
          Route trace
        </span>
        <RouteTraceInline trace={trace} />
      </summary>
      <div
        style={{
          marginTop: 8,
          display: 'grid',
          gridTemplateColumns: 'auto 1fr',
          rowGap: 4,
          columnGap: 12,
          fontSize: 11.5,
        }}
      >
        <DiagLabel>nodes</DiagLabel>
        <RouteTraceInline trace={trace} expanded />
        {message.category && (
          <>
            <DiagLabel>category</DiagLabel>
            <DiagValue>{message.category}</DiagValue>
          </>
        )}
        {message.intent && (
          <>
            <DiagLabel>intent</DiagLabel>
            <DiagValue>{message.intent}</DiagValue>
          </>
        )}
        {message.severity && (
          <>
            <DiagLabel>severity</DiagLabel>
            <DiagValue>{message.severity}</DiagValue>
          </>
        )}
        {message.urgency && (
          <>
            <DiagLabel>urgency</DiagLabel>
            <DiagValue>{message.urgency}</DiagValue>
          </>
        )}
        {ticketReason && (
          <>
            <DiagLabel>ticket</DiagLabel>
            <DiagValue>{ticketReason}</DiagValue>
          </>
        )}
        {automationStatus && (
          <>
            <DiagLabel>automation</DiagLabel>
            <DiagValue>
              {automationStatus}
              {message.automationSimulated ? ' · simulated' : ''}
            </DiagValue>
          </>
        )}
      </div>
    </details>
  );
}

function RouteTraceInline({ trace, expanded = false }) {
  return (
    <span
      style={{
        display: 'inline-flex',
        flexWrap: 'wrap',
        gap: 4,
        alignItems: 'center',
        fontFamily: 'var(--font-mono, monospace)',
      }}
    >
      {trace.map((node, idx) => (
        <span key={idx} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          <span
            className="mono"
            style={{
              fontSize: 11,
              padding: '1px 6px',
              borderRadius: 4,
              background: expanded ? 'var(--surface)' : '#eef2f7',
              color: 'var(--text-secondary)',
              border: '1px solid var(--border)',
            }}
          >
            {node}
          </span>
          {idx < trace.length - 1 && (
            <span style={{ color: 'var(--text-faint)', fontSize: 11 }}>→</span>
          )}
        </span>
      ))}
    </span>
  );
}

function DiagLabel({ children }) {
  return (
    <span
      style={{
        color: 'var(--text-muted)',
        fontSize: 10.5,
        fontWeight: 600,
        letterSpacing: 0.5,
        textTransform: 'uppercase',
        whiteSpace: 'nowrap',
      }}
    >
      {children}
    </span>
  );
}

function DiagValue({ children }) {
  return (
    <span className="mono" style={{ fontSize: 11.5, color: 'var(--text)' }}>
      {children}
    </span>
  );
}

function FeedbackButtons({ messageId, current, onFeedback }) {
  const baseStyle = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: 26,
    height: 26,
    background: 'transparent',
    border: '1px solid var(--border)',
    borderRadius: 6,
    cursor: 'pointer',
    color: 'var(--text-muted)',
    transition: 'all 120ms ease',
  };
  const activeUp = {
    background: 'var(--green-soft)',
    borderColor: '#6ee7b7',
    color: '#047857',
  };
  const activeDown = {
    background: 'var(--red-soft)',
    borderColor: '#fca5a5',
    color: '#b91c1c',
  };
  return (
    <div style={{ display: 'flex', gap: 4, marginLeft: 'auto' }}>
      <button
        type="button"
        aria-label="Helpful"
        title="Helpful"
        onClick={() => onFeedback(messageId, 'up')}
        disabled={current === 'up'}
        style={{ ...baseStyle, ...(current === 'up' ? activeUp : {}) }}
      >
        <ThumbsUp />
      </button>
      <button
        type="button"
        aria-label="Not helpful"
        title="Not helpful"
        onClick={() => onFeedback(messageId, 'down')}
        disabled={current === 'down'}
        style={{ ...baseStyle, ...(current === 'down' ? activeDown : {}) }}
      >
        <ThumbsDown />
      </button>
    </div>
  );
}

function ThumbsUp() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
      <path
        d="M7 11v9H4v-9h3zM7 11l4-7c1.5 0 2 1 2 2v4h5a2 2 0 0 1 2 2.3l-1 5a2 2 0 0 1-2 1.7H7"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ThumbsDown() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
      <path
        d="M17 13V4h3v9h-3zM17 13l-4 7c-1.5 0-2-1-2-2v-4H6a2 2 0 0 1-2-2.3l1-5A2 2 0 0 1 7 5h10"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function Sources({ sources }) {
  return (
    <div
      style={{
        maxWidth: '84%',
        background: 'var(--surface-soft)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-md)',
        padding: '10px 14px',
        fontSize: 12.5,
        color: 'var(--text-secondary)',
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
      }}
    >
      <div
        style={{
          fontSize: 10.5,
          fontWeight: 600,
          color: 'var(--text-muted)',
          letterSpacing: 0.6,
          textTransform: 'uppercase',
        }}
      >
        Sources
      </div>
      {sources.map((s) => (
        <div
          key={s.chunk_id || s.doc_id}
          style={{ display: 'flex', gap: 10, alignItems: 'center' }}
        >
          <span
            className="mono"
            style={{
              color: 'var(--text)',
              minWidth: 64,
              fontSize: 11.5,
              fontWeight: 500,
            }}
          >
            {s.doc_id}
          </span>
          <span style={{ flex: 1, color: 'var(--text-secondary)' }}>{s.title}</span>
        </div>
      ))}
    </div>
  );
}

// ---------- markdown renderer (no external deps) ----------

function inlineMarkdown(text, key = 0) {
  const segments = [];
  const re = /(\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`)/g;
  let last = 0;
  let m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) segments.push(text.slice(last, m.index));
    if (m[2] !== undefined) segments.push(<strong key={m.index}>{m[2]}</strong>);
    else if (m[3] !== undefined) segments.push(<em key={m.index}>{m[3]}</em>);
    else if (m[4] !== undefined)
      segments.push(
        <code
          key={m.index}
          style={{
            background: 'var(--surface-soft)',
            border: '1px solid var(--border)',
            borderRadius: 4,
            padding: '1px 5px',
            fontSize: '0.88em',
            fontFamily: 'monospace',
          }}
        >
          {m[4]}
        </code>,
      );
    last = m.index + m[0].length;
  }
  if (last < text.length) segments.push(text.slice(last));
  return segments.length === 0 ? (
    ''
  ) : segments.length === 1 && typeof segments[0] === 'string' ? (
    segments[0]
  ) : (
    <span key={key}>{segments}</span>
  );
}

function MarkdownContent({ content }) {
  const lines = (content || '').split('\n');
  const nodes = [];
  let i = 0;

  while (i < lines.length) {
    const raw = lines[i];
    const stripped = raw.trimStart();

    if (/^#{1,3}\s/.test(stripped)) {
      const level = stripped.match(/^(#{1,3})/)[1].length;
      const text = stripped.replace(/^#{1,3}\s+/, '');
      nodes.push(
        <div
          key={i}
          style={{
            fontWeight: 600,
            fontSize: level === 1 ? 16 : level === 2 ? 15 : 14,
            marginTop: nodes.length ? 10 : 0,
            marginBottom: 2,
            color: 'var(--text)',
          }}
        >
          {inlineMarkdown(text, i)}
        </div>,
      );
    } else if (/^[-*•]\s/.test(stripped)) {
      nodes.push(
        <div key={i} style={{ display: 'flex', gap: 8, paddingLeft: 8 }}>
          <span style={{ color: 'var(--text-muted)', flexShrink: 0, marginTop: 1 }}>•</span>
          <span>{inlineMarkdown(stripped.replace(/^[-*•]\s+/, ''), i)}</span>
        </div>,
      );
    } else if (/^\d+\.\s/.test(stripped)) {
      const num = stripped.match(/^(\d+)\./)[1];
      nodes.push(
        <div key={i} style={{ display: 'flex', gap: 8, paddingLeft: 8 }}>
          <span
            style={{
              color: 'var(--text-muted)',
              flexShrink: 0,
              minWidth: 18,
              textAlign: 'right',
              marginTop: 1,
            }}
          >
            {num}.
          </span>
          <span>{inlineMarkdown(stripped.replace(/^\d+\.\s+/, ''), i)}</span>
        </div>,
      );
    } else if (stripped === '') {
      if (nodes.length && nodes[nodes.length - 1]?.key !== `gap-${i - 1}`) {
        nodes.push(<div key={`gap-${i}`} style={{ height: 6 }} />);
      }
    } else {
      nodes.push(<div key={i}>{inlineMarkdown(raw, i)}</div>);
    }
    i++;
  }

  return <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>{nodes}</div>;
}

function ThinkingIndicator() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, paddingLeft: 4 }}>
      <Avatar />
      <div
        style={{
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          borderRadius: '4px 14px 14px 14px',
          padding: '10px 14px',
          display: 'flex',
          gap: 4,
          boxShadow: 'var(--shadow-xs)',
        }}
      >
        <Dot delay={0} />
        <Dot delay={150} />
        <Dot delay={300} />
      </div>
      <style>{`
        @keyframes pulseDot {
          0%, 80%, 100% { opacity: 0.25; transform: translateY(0); }
          40% { opacity: 1; transform: translateY(-2px); }
        }
      `}</style>
    </div>
  );
}

function Dot({ delay }) {
  return (
    <span
      style={{
        width: 6,
        height: 6,
        borderRadius: '50%',
        background: 'var(--text-faint)',
        animation: `pulseDot 1.2s ${delay}ms ease-in-out infinite`,
        display: 'inline-block',
      }}
    />
  );
}

function Avatar() {
  return (
    <div
      style={{
        width: 24,
        height: 24,
        borderRadius: 7,
        background: 'linear-gradient(135deg, #3b82f6 0%, #0d9488 100%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        boxShadow: 'inset 0 0 0 1px rgba(255,255,255,0.15)',
      }}
    >
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
        <path
          d="M12 3l1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7L12 3z"
          stroke="#fff"
          strokeWidth="1.8"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  );
}

function Composer({ input, setInput, onSubmit, isLoading }) {
  return (
    <form
      onSubmit={onSubmit}
      style={{
        padding: '16px 32px 24px',
        background: 'var(--bg)',
        borderTop: '1px solid var(--border)',
      }}
    >
      <div
        style={{
          maxWidth: 760,
          margin: '0 auto',
          display: 'flex',
          gap: 8,
          alignItems: 'stretch',
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          borderRadius: 12,
          padding: 6,
          boxShadow: 'var(--shadow-sm)',
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
            padding: '10px 12px',
            border: 'none',
            outline: 'none',
            background: 'transparent',
            fontSize: 14,
            color: 'var(--text)',
          }}
        />
        <button
          type="submit"
          disabled={isLoading || !input.trim()}
          style={{
            padding: '8px 16px',
            background: isLoading || !input.trim() ? '#cbd5e1' : 'var(--brand)',
            color: '#ffffff',
            border: 'none',
            borderRadius: 8,
            fontSize: 13,
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            transition: 'background 120ms ease',
          }}
          onMouseOver={(e) => {
            if (!isLoading && input.trim()) e.currentTarget.style.background = 'var(--brand-hover)';
          }}
          onMouseOut={(e) => {
            if (!isLoading && input.trim()) e.currentTarget.style.background = 'var(--brand)';
          }}
        >
          {isLoading ? 'Sending…' : 'Send'}
          {!isLoading && (
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
              <path
                d="M5 12h14M13 6l6 6-6 6"
                stroke="#fff"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          )}
        </button>
      </div>
      <div
        style={{
          maxWidth: 760,
          margin: '8px auto 0',
          fontSize: 11.5,
          color: 'var(--text-muted)',
          textAlign: 'center',
        }}
      >
        The assistant uses your KB + Claude. Tickets are only opened for unresolved issues.
      </div>
    </form>
  );
}

// ---------- shared chip + glyph ----------

function chipKindForMatch(strength) {
  if (strength === 'strong') return 'teal';
  if (strength === 'weak') return 'amber';
  return 'neutral';
}

function Chip({ kind = 'neutral', children }) {
  const palette = {
    teal: { bg: 'var(--teal-soft)', color: '#115e59', border: '#5eead4' },
    amber: { bg: 'var(--amber-soft)', color: '#92400e', border: '#fcd34d' },
    red: { bg: 'var(--red-soft)', color: '#991b1b', border: '#fca5a5' },
    blue: { bg: 'var(--brand-soft)', color: '#1e40af', border: '#bfdbfe' },
    green: { bg: 'var(--green-soft)', color: '#065f46', border: '#6ee7b7' },
    neutral: { bg: '#f1f5f9', color: '#334155', border: '#cbd5e1' },
  }[kind];
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        padding: '3px 9px',
        borderRadius: 999,
        background: palette.bg,
        color: palette.color,
        border: `1px solid ${palette.border}`,
        fontSize: 11.5,
        fontWeight: 500,
        whiteSpace: 'nowrap',
      }}
    >
      {children}
    </span>
  );
}

function DotIcon() {
  return (
    <span
      style={{
        width: 6,
        height: 6,
        borderRadius: '50%',
        background: 'currentColor',
        opacity: 0.85,
      }}
    />
  );
}

function TicketGlyph() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none">
      <path
        d="M4 8a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v2a2 2 0 0 0 0 4v2a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-2a2 2 0 0 0 0-4V8z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
    </svg>
  );
}

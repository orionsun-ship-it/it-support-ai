import { useEffect, useMemo, useState } from "react";

const CATEGORY_COLORS = {
  password: { bg: "var(--brand-soft)", color: "#1e40af", border: "#bfdbfe" },
  network: { bg: "var(--teal-soft)", color: "#115e59", border: "#5eead4" },
  software: { bg: "#ede9fe", color: "#5b21b6", border: "#c4b5fd" },
  hardware: { bg: "var(--amber-soft)", color: "#92400e", border: "#fcd34d" },
  access: { bg: "var(--green-soft)", color: "#065f46", border: "#6ee7b7" },
  other: { bg: "#f1f5f9", color: "#334155", border: "#cbd5e1" },
};

export default function SourcesPage() {
  const [docs, setDocs] = useState([]);
  const [files, setFiles] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");
  const [openId, setOpenId] = useState(null);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch("/api/sources");
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setDocs(Array.isArray(data.documents) ? data.documents : []);
      setFiles(Array.isArray(data.files) ? data.files : []);
    } catch (err) {
      setError(err.message || String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const categories = useMemo(() => {
    const set = new Set(docs.map((d) => d.category || "other"));
    return ["all", ...Array.from(set).sort()];
  }, [docs]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return docs.filter((d) => {
      if (filter !== "all" && (d.category || "other") !== filter) return false;
      if (!q) return true;
      return (
        (d.title || "").toLowerCase().includes(q) ||
        (d.doc_id || "").toLowerCase().includes(q) ||
        (d.body || "").toLowerCase().includes(q)
      );
    });
  }, [docs, filter, query]);

  return (
    <div style={{ padding: "32px 32px 40px", maxWidth: 1180, margin: "0 auto" }}>
      <div
        style={{
          display: "flex",
          alignItems: "flex-end",
          justifyContent: "space-between",
          gap: 16,
        }}
      >
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
            Knowledge sources
          </h2>
          <div style={{ marginTop: 4, color: "var(--text-muted)", fontSize: 13.5 }}>
            All KB documents the assistant can cite.{" "}
            {files.length > 0 && (
              <span>
                Loaded from{" "}
                <span className="mono" style={{ color: "var(--text-secondary)" }}>
                  {files.join(", ")}
                </span>
                .
              </span>
            )}
          </div>
        </div>

        <button
          onClick={refresh}
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
          }}
        >
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      <div
        style={{
          marginTop: 20,
          display: "flex",
          gap: 12,
          alignItems: "center",
          flexWrap: "wrap",
        }}
      >
        <input
          placeholder="Search title, ID, or body…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{
            flex: 1,
            minWidth: 240,
            padding: "9px 12px",
            border: "1px solid var(--border-strong)",
            borderRadius: 8,
            background: "var(--surface)",
            fontSize: 13,
            color: "var(--text)",
            outline: "none",
            boxShadow: "var(--shadow-xs)",
          }}
        />
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {categories.map((c) => {
            const active = filter === c;
            return (
              <button
                key={c}
                onClick={() => setFilter(c)}
                style={{
                  padding: "6px 12px",
                  background: active ? "var(--brand)" : "var(--surface)",
                  color: active ? "#fff" : "var(--text-secondary)",
                  border: `1px solid ${
                    active ? "var(--brand)" : "var(--border-strong)"
                  }`,
                  borderRadius: 999,
                  fontSize: 12,
                  fontWeight: 500,
                  textTransform: "capitalize",
                }}
              >
                {c}
              </button>
            );
          })}
        </div>
        <div
          style={{
            marginLeft: "auto",
            fontSize: 12.5,
            color: "var(--text-muted)",
          }}
        >
          {filtered.length} of {docs.length} document
          {docs.length === 1 ? "" : "s"}
        </div>
      </div>

      {error && (
        <div
          style={{
            marginTop: 20,
            background: "var(--red-soft)",
            color: "#991b1b",
            padding: 16,
            borderRadius: "var(--radius-md)",
            border: "1px solid #fca5a5",
            fontSize: 13,
          }}
        >
          Failed to load sources: {error}
        </div>
      )}

      <div
        style={{
          marginTop: 20,
          display: "flex",
          flexDirection: "column",
          gap: 10,
        }}
      >
        {!loading && filtered.length === 0 && !error && (
          <div
            style={{
              padding: 32,
              textAlign: "center",
              color: "var(--text-muted)",
              border: "1px dashed var(--border)",
              borderRadius: "var(--radius-md)",
              background: "var(--surface)",
              fontSize: 13.5,
            }}
          >
            No documents match those filters.
          </div>
        )}

        {filtered.map((d) => (
          <DocCard
            key={d.doc_id}
            doc={d}
            open={openId === d.doc_id}
            onToggle={() => setOpenId(openId === d.doc_id ? null : d.doc_id)}
          />
        ))}
      </div>
    </div>
  );
}

function DocCard({ doc, open, onToggle }) {
  const cat = CATEGORY_COLORS[doc.category] || CATEGORY_COLORS.other;
  return (
    <div
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-lg)",
        boxShadow: "var(--shadow-xs)",
        overflow: "hidden",
        transition: "border-color 120ms ease",
      }}
    >
      <button
        onClick={onToggle}
        style={{
          width: "100%",
          textAlign: "left",
          padding: "14px 18px",
          background: "transparent",
          border: "none",
          display: "flex",
          alignItems: "center",
          gap: 14,
          color: "var(--text)",
        }}
      >
        <span
          className="mono"
          style={{
            background: "#f1f5f9",
            padding: "3px 8px",
            borderRadius: 6,
            fontSize: 12,
            fontWeight: 500,
            color: "#0f172a",
            minWidth: 72,
            textAlign: "center",
          }}
        >
          {doc.doc_id}
        </span>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              fontWeight: 600,
              fontSize: 14,
              color: "var(--text)",
              letterSpacing: -0.1,
            }}
          >
            {doc.title}
          </div>
          {doc.body && (
            <div
              style={{
                marginTop: 3,
                fontSize: 12.5,
                color: "var(--text-muted)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {doc.body.slice(0, 160)}
            </div>
          )}
        </div>

        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            padding: "3px 9px",
            borderRadius: 6,
            background: cat.bg,
            color: cat.color,
            border: `1px solid ${cat.border}`,
            fontSize: 11,
            fontWeight: 600,
            textTransform: "uppercase",
            letterSpacing: 0.4,
          }}
        >
          {doc.category || "other"}
        </span>

        {doc.version && (
          <span
            className="mono"
            style={{ fontSize: 11.5, color: "var(--text-muted)", minWidth: 78, textAlign: "right" }}
          >
            v{doc.version}
          </span>
        )}

        <Chevron open={open} />
      </button>

      {open && (
        <div
          style={{
            padding: "12px 18px 18px",
            borderTop: "1px solid var(--border)",
            background: "var(--surface-soft)",
            color: "var(--text-secondary)",
            fontSize: 13.5,
            lineHeight: 1.65,
            whiteSpace: "pre-wrap",
          }}
        >
          {doc.body || "(no body)"}
          {(doc.source || doc.source_file) && (
            <div
              style={{
                marginTop: 14,
                paddingTop: 12,
                borderTop: "1px solid var(--border)",
                display: "flex",
                gap: 16,
                fontSize: 11.5,
                color: "var(--text-muted)",
              }}
            >
              {doc.source && (
                <span>
                  Source:{" "}
                  <span className="mono" style={{ color: "var(--text-secondary)" }}>
                    {doc.source}
                  </span>
                </span>
              )}
              {doc.source_file && (
                <span>
                  File:{" "}
                  <span className="mono" style={{ color: "var(--text-secondary)" }}>
                    {doc.source_file}
                  </span>
                </span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Chevron({ open }) {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      style={{
        transition: "transform 150ms ease",
        transform: open ? "rotate(180deg)" : "none",
        color: "var(--text-muted)",
      }}
    >
      <path
        d="M6 9l6 6 6-6"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

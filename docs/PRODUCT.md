# Product brief — IT Support AI

This brief is the **product owner's view** of the system: who it serves,
what problems it solves, what success looks like, what's in / out of scope,
and the rationale behind the architecture choices. The implementation
details are elsewhere in the repo (see `README.md` and the other docs).

This brief covers grading checkpoints **1 (Problem definition)**,
**2 (Product ownership)** and **4 (RAG integration)**. Architecture and
testing are covered separately.

---

## 1. Problem we are solving

### 1.1 The user pain (mid-sized internal IT)

A typical mid-market company (1k–10k employees) runs a small IT desk
(8–20 agents) facing a long tail of repetitive requests:

- "I forgot my password / my account is locked."
- "My VPN won't connect / it's slow."
- "Outlook won't open / installer error 1603."
- "I need access to repo X / database Y / SaaS Z."
- "Software install: Slack / Figma / a Python."
- "What's the status of my open ticket?"

Internal benchmarking and the public ServiceNow / Zendesk reports we cite
in [`INDUSTRY_COMPARISON.md`](INDUSTRY_COMPARISON.md) show the pattern:

- **40–60 % of all IT tickets** are recurring and resolvable from existing
  documented procedures.
- Average **first-response time** for tier-1 IT is 30–90 minutes during
  business hours, rising to 8+ hours overnight or near holidays — even when
  the resolution itself is a one-liner from a runbook.
- Agents context-switch between **multiple tools**: ITSM (ServiceNow /
  Jira / Freshservice), identity (Okta / Entra), SaaS access portals,
  knowledge bases, and chat. Every context switch is friction.
- Knowledge bases are usually **out of date**, and even when fresh, agents
  don't reliably search them — they fall back to muscle memory and
  internal Slack pings.

The cost of not solving this: lost engineer time, a long shadow tier-2
queue ("waiting on IT"), and an IT team that burns out on tickets they
shouldn't have to touch.

### 1.2 Who we serve

| Persona                 | What they want                                                                  |
| ----------------------- | ------------------------------------------------------------------------------- |
| **End user** (employee) | Fast, accurate answer to a simple IT issue without a ticket round-trip.         |
| **Tier-1 IT agent**     | Auto-resolve the easy cases; auto-summarise the hard ones; one source of truth. |
| **IT manager**          | Lower MTTR, fewer escalations, visibility into where people are stuck.          |
| **Compliance / audit**  | An auditable trail of who did what, when, and why — including AI actions.       |

This MVP focuses on the **end user** first (chat UI, automated resolution
where safe) and the **agent / manager** second (Tickets and Metrics views,
audit log via the IT Ops API).

### 1.3 Use case in scope (capstone slice)

The slice we ship in this capstone:

- A web chat assistant the end user opens.
- Multi-agent pipeline: classify → ground in KB → run safe automations →
  decide whether to open a ticket → escalate cleanly when needed.
- A real ticket DB with full event + audit trail.
- The same tool surface exposed via Model Context Protocol so it can be
  driven from VS Code Copilot Chat or Claude Desktop without any new
  integration code.

Out of scope (intentionally) for the capstone:

- Real identity / asset / access integrations (those are stubbed; see
  the README's "Simulated automations" section).
- Single sign-on / RBAC (the IT Ops API uses a shared service token for
  the local demo; production would terminate user identity at the
  backend boundary).
- Multi-tenant deployment, alerting, paging.

---

## 2. Success metrics

We separate **product metrics** (does the user get help?) from **system
metrics** (does the routing actually do what we say it does?).

### 2.1 Product metrics (target after pilot)

| Metric                              | Definition                                            | Target  |
| ----------------------------------- | ----------------------------------------------------- | ------- |
| **Self-serve resolution rate**      | % of conversations that end without escalation.       | ≥ 60 %  |
| **First-response time (assistant)** | Time from user message to first assistant reply.      | < 10 s  |
| **Avg time-to-resolve (assistant)** | For self-served conversations, time to last message.  | < 2 min |
| **CSAT (👍 / 👍+👎)**               | Per-turn feedback recorded via the Feedback endpoint. | ≥ 80 %  |
| **Escalation precision**            | % of escalated tickets that the human agent agrees    | ≥ 90 %  |
|                                     | were appropriate to escalate.                         |         |

### 2.2 System metrics (already enforced in tests)

These ensure the routing behaves the way we promise. Every PR runs the
deterministic harness; the live-LLM harness runs on demand.

| Axis                                        | Target | Measured by               |
| ------------------------------------------- | ------ | ------------------------- |
| Correct route trace                         | 100 %  | `tests/test_routing.py`   |
| Correct ticket-creation decision            | 100 %  | `tests/test_routing.py`   |
| Correct escalation decision                 | 100 %  | `tests/test_routing.py`   |
| Correct automation status                   | 100 %  | `tests/test_routing.py`   |
| MCP↔HTTP cross-transport parity             | 100 %  | `tests/test_mcp_proof.py` |
| Category classification accuracy (live LLM) | ≥ 85 % | `tests/test_accuracy.py`  |

See [`VALIDATION.md`](VALIDATION.md) for the latest results.

### 2.3 What we won't measure (yet)

Anything that requires a deployed environment with real users — funnel
conversion, deflection vs. existing ITSM, agent time saved, etc. Those
are pilot metrics, not capstone metrics. We instrument for them (the
`/metrics` endpoint exposes request count, escalations, satisfaction)
so a pilot is a config change, not a code change.

---

## 3. Product ownership perspective

### 3.1 Why a multi-agent pipeline (not one big LLM call)

A single-LLM "answer the IT question" prompt would have worked for ~70 %
of cases. We chose four small agents instead because:

- **Predictable routing**. One agent decides "is this a support request,
  what kind, how urgent". Another decides "is the answer in the KB". The
  workflow agent is the only one that can mutate the world (open a
  ticket, run an automation). Splitting these is the cheapest way to
  bound risk and make the system testable.
- **Auditable behaviour**. The chat UI shows the actual route trace
  (`intake → knowledge → workflow → final_response`) so a grader, a
  compliance reviewer, or a curious user can see what the system did,
  not just what it said.
- **Independent failure modes**. The Knowledge agent can degrade
  gracefully (weak match → "best-effort general answer + check-in
  question") without bringing down the workflow agent. The IT Ops API
  can be unavailable and the Workflow agent falls back to a local
  ticket id (`LOCAL-...`) instead of crashing.
- **Right tool for the right step**. Intake is a structured-output
  classifier; Knowledge is RAG; Workflow is rule-based; Escalation is
  policy. Putting all of those behind one prompt would over-couple them.

### 3.2 Why ground answers in a real KB (RAG)

We picked sentence-transformers + ChromaDB instead of just trusting the
model's prior knowledge for three product reasons:

- **Citations build trust**. The chat UI surfaces `[doc-id] title`
  alongside every grounded answer. End users learn the assistant is
  pointing at the company's actual runbook, not making things up.
- **Updates are a JSON edit**. KB content is a JSON file under
  `backend/data/kb/`. The ingest pipeline diff-hashes each chunk with
  SHA-256 so only changed content is re-embedded. The IT documentation
  team can own KB updates without touching agent code.
- **Honest fallback on weak matches**. When retrieval returns nothing
  strong, the Knowledge agent doesn't refuse — it gives best-effort
  general advice **and** asks one specific check-in question
  ("Did that resolve your issue?"). If the user says it didn't, the
  routing escalates. That's the right product shape: helpful by default,
  human-in-the-loop when stuck.

The KB ships with **130 documents** spanning password, access, software,
hardware, network, email, vpn, security, mobile, remote, printing,
endpoint, storage, collaboration, onboarding, compliance, and operations.
That's deliberately broader than the routing schema so retrieval keeps
working when intake misclassifies.

### 3.3 Why MCP

The Model Context Protocol gives us **one tool contract, many clients**.
The same `create_ticket` capability is callable from:

- The LangGraph agent (in-process, via the IT Ops HTTP API).
- VS Code Copilot Chat (over stdio MCP).
- Claude Desktop (over stdio MCP).
- A future ChatOps bot, internal CLI, or third-party MCP-aware tool — at
  zero integration cost.

Without MCP, every new client we want to support would need to learn the
HTTP shape, the auth header, the JSON contract, the error semantics.
With MCP, the server publishes a typed manifest and clients discover the
tools at runtime.

Importantly, MCP also lets us **compose**: in
[`MCP_VSCode_Demo.md`](MCP_VSCode_Demo.md) we show wiring the official
GitHub MCP server alongside ours so an editor can `create_issue` on
GitHub and `create_ticket` on our IT desk through the same protocol. That
is the practical demonstration of vendor-neutral standardisation.

### 3.4 Scope discipline (what we said no to)

| Idea                                                  | Why we said no (for MVP)                                   |
| ----------------------------------------------------- | ---------------------------------------------------------- |
| LLM-driven routing (let the model pick the next node) | Less predictable, harder to test, harder to audit.         |
| Auto-resolution of access requests without approval   | The blast radius is high; the value is low for capstone.   |
| Real Okta / Entra / Slack / Jira integrations         | Stubs preserve the architectural shape; real adapters can  |
|                                                       | be added per-intent in `workflow_agent.py` without churn.  |
| Multi-tenant deployment story                         | Single-tenant assumption made the auth + CORS story clean. |
| Voice / Slack channels                                | Same backend would serve them; UI surface is the change.   |

### 3.5 Roadmap (phase 2 / pilot)

In rough priority order:

1. Real adapters for `password_reset`, `account_unlock`, `software_install`
   (Okta / Entra / Intune). These are the highest-volume intents.
2. A real "ticket follow-up" loop — the Workflow agent already opens
   tickets, but a second agent should poll for resolution, ping the user,
   and close them.
3. Move sessions to Redis and tickets to Postgres; dual-write to BigQuery
   for analytics.
4. Slack / Teams surface in addition to the web chat.
5. Pilot rollout: 50 employees, two weeks, weekly metrics review against
   §2.1.

---

## 4. RAG integration in detail

A short section because it gets its own grading checkpoint.

### 4.1 Pipeline

```
KB JSON files  ───► chunker (600-char window, 80-char overlap)
   │                       │
   │                       ▼
   │                SHA-256 hash ───► skip if unchanged
   │                       │
   ▼                       ▼
sentence-transformers   ChromaDB upsert (id = doc_id::chunk-N)
all-MiniLM-L6-v2
   │
   ▼
KnowledgeRetriever  ───► distance threshold (default 0.85) ──► strong / weak / none
   │                                                              │
   ├── category filter (when intake confidence ≥ 0.7)              │
   ├── keyword rescue for known error codes (1603, 0x..., …)       │
   └── fallback: retry without category filter on empty result     ▼
                                                          Knowledge agent
                                                              │
                                          ┌──── strong ──────┴──── weak/none ────┐
                                          ▼                                       ▼
                                  GROUNDED_PROMPT                       NO_MATCH_PROMPT
                                  (cites [doc_id] per step)             (best-effort + check-in)
```

Code: `backend/rag/{ingest,vector_store,retriever,embedder}.py`.

### 4.2 Why these choices

- **Sentence-transformers `all-MiniLM-L6-v2`**: small, free, fast on CPU,
  good enough for short IT runbook chunks. We don't need OpenAI embeddings
  for 130 docs.
- **600-char windows with 80-char overlap**: matches the average length
  of a single procedure step in our KB. Smaller windows fragment a single
  procedure; larger ones dilute relevance.
- **SHA-256 content hashing**: the ingest pipeline only re-embeds chunks
  whose content changed. A doc-content edit is fast; a no-op re-run is
  free.
- **Distance threshold + keyword rescue**: pure-vector retrieval misses
  exact tokens like `1603` or `PAGE_FAULT_IN_NONPAGED_AREA` when paraphrased.
  We add a regex pass that rescues hits containing the literal token. This
  is a small, pragmatic hybrid retrieval.
- **Category filter as a **soft** prior**: we apply the category filter
  only when intake confidence ≥ 0.7, and we re-query without the filter
  if the filtered query returns nothing. This stops a misclassification
  from killing retrieval.

### 4.3 What good RAG looks like in this product

We treat retrieval quality as a product feature, not a model property.
Concretely:

- The chat UI surfaces every cited source with `doc_id` + title under
  each grounded answer.
- The Sources page (`/sources`) lists every KB document on disk so the
  documentation owner can see the full corpus.
- The `/debug/retrieve?query=...` endpoint (gated by `ENABLE_DEBUG_ENDPOINTS`)
  shows raw distances and snippets for any query — operators can sanity-
  check the retriever in production.
- Match strength (`strong | weak | none`) is part of the API response
  and shown as a chip in the chat UI. The user sees "kb match · weak"
  and the agent has explicitly degraded into best-effort mode.

This is intentional: the user, the operator, and the grader all see the
same retrieval signal.

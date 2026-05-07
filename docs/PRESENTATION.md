# IT Support AI — capstone presentation deck

A self-contained slide deck a presenter can read top-to-bottom in ~10
minutes. Each `## Slide N — Title` is one slide. Speaker notes live
under each slide, indented as a quote block.

The deck mirrors the eight grading checkpoints. Cross-references point
at the deeper docs for graders who want to dig.

---

## Slide 1 — Title & one-line pitch

**IT Support AI** — A multi-agent, RAG-grounded, MCP-standardised IT
support assistant. *Auto-resolve the resolvable, escalate the rest
cleanly.*

> The pitch in one breath: most IT tickets are repetitive and
> answerable from a runbook. This system answers them in chat, runs safe
> automations where allowed, and escalates the rest with full context.
> The differentiator is that every tool is reachable through the Model
> Context Protocol — the same `create_ticket` works from a web chat,
> from VS Code, from Claude Desktop, with one server.

---

## Slide 2 — The problem (Checkpoint 1)

- 1k–10k-employee companies field a long tail of repetitive IT requests:
  password resets, VPN hiccups, software access, account unlocks.
- 40–60 % of these are resolvable from documented procedures.
- First-response times are 30–90 minutes during the day, 8+ hours
  overnight — even when the fix is a one-liner.
- Agents context-switch between ITSM, identity, KB, and chat. Every
  switch is friction.

> Think of the typical IT ticket queue: 60 % is "I forgot my password"
> and 5 % is the actual hard problem. Today the 5 % gets buried under
> the 60. We want to automate the 60 so the 5 gets attention faster.

Deep dive: [`PRODUCT.md`](PRODUCT.md) §1 (Pain points + personas).

---

## Slide 3 — Success metrics (Checkpoint 1)

| Axis                                | Target | Measured by                  |
| ----------------------------------- | ------ | ---------------------------- |
| Self-serve resolution rate          | ≥ 60 % | Pilot                        |
| First response (assistant)          | < 10 s | Pilot                        |
| Avg time-to-resolve (self-served)   | < 2 min| Pilot                        |
| CSAT (👍 / 👍+👎)                   | ≥ 80 % | `/feedback` endpoint         |
| Routing correctness (every branch)  | 100 %  | `tests/test_routing.py`      |
| Category classification (live LLM)  | ≥ 85 % | `tests/test_accuracy.py`     |
| MCP↔HTTP cross-transport parity     | 100 %  | `tests/test_mcp_proof.py`    |

> System metrics are already enforced — the deterministic harness blocks
> regressions on every PR. Product metrics need a pilot but the
> instrumentation is already in place.

Deep dive: [`PRODUCT.md`](PRODUCT.md) §2.

---

## Slide 4 — Product ownership view (Checkpoint 2)

- **Multi-agent over single LLM** — predictable routing, auditable
  behaviour, independent failure modes.
- **RAG with cited sources** — citations build trust; the doc team owns
  KB updates without code changes; weak matches degrade honestly into
  best-effort + check-in.
- **MCP as the integration boundary** — one tool contract, many clients
  (web chat, VS Code, Claude Desktop, future Slack / voice).
- **Stubbed automations, real shape** — the architecture has a place
  for every production adapter; we shipped the placeholders so the
  topology is real.
- **Out-of-scope, on purpose** — no SSO/RBAC, no multi-tenant, no
  third-party integrations, no analytics suite. We picked depth over
  breadth.

> The job of the product owner here was to keep the surface small. It
> would have been easy to ship 10 mediocre features. We shipped 4
> agents that route well, RAG that cites well, and MCP that proves
> well.

Deep dive: [`PRODUCT.md`](PRODUCT.md) §3.

---

## Slide 5 — Agent architecture (Checkpoint 3)

```
START → intake →┬─ non-support → final_response
                └─ otherwise   → knowledge

knowledge →┬─ ticket_request OR requires_automation → workflow
           ├─ stuck OR asks for human               → escalation
           └─ otherwise                              → final_response

workflow  →┬─ failed / manual_required               → escalation
           ├─ severity=critical OR urgency=high      → escalation
           └─ otherwise                              → final_response

escalation → final_response → END
```

- **Intake** — structured-output classifier (category, intent,
  severity, urgency, confidence, is_support_request).
- **Knowledge** — RAG over ChromaDB; grounded answer on strong match,
  best-effort + check-in on weak/none.
- **Workflow** — runs intent-based safe automations; opens a ticket
  only when needed.
- **Escalation** — explicit rules; bumps priority; specific human
  handoff message.

> One agent = one decision. Routing functions in the orchestrator are
> pure (read state, return next-node name) and tested in isolation.

Deep dive: [`../diagrams/architecture.md`](../diagrams/architecture.md).

---

## Slide 6 — RAG pipeline (Checkpoint 4)

- **130 KB documents** under `backend/data/kb/` (JSON, doc-team-owned).
- **Chunker**: 600-char windows, 80-char overlap; SHA-256 hash so
  unchanged chunks aren't re-embedded.
- **Embeddings**: `sentence-transformers/all-MiniLM-L6-v2` — small,
  free, CPU-fast.
- **Store**: ChromaDB persistent, with a self-recovery path if the
  on-disk format is incompatible.
- **Retrieval**: distance threshold (default 0.85) → strong / weak /
  none; soft category filter when intake confidence ≥ 0.7; keyword
  rescue for known error tokens (`1603`, `0x...`, `PAGE_FAULT_...`).
- **Cited sources** surfaced in the chat UI for every grounded answer.

> The KB is intentionally broader than the intake schema — retrieval
> stays useful even when intake misclassifies the category. That's a
> small product decision with outsized robustness gains.

Deep dive: [`PRODUCT.md`](PRODUCT.md) §4.

---

## Slide 7 — Workflow automation (Checkpoint 5)

| Intent                  | Status      | What it does                                        |
| ----------------------- | ----------- | --------------------------------------------------- |
| `password_reset`        | Simulated   | Returns a `[Simulated]` reset-link confirmation.    |
| `account_unlock`        | Simulated   | Returns a `[Simulated]` unlock confirmation.        |
| `software_license_check`| Simulated   | Returns a `[Simulated]` license-active answer.      |
| `software_install`      | Simulated   | Returns a `[Simulated]` install-request answer.     |
| `access_request`        | Simulated   | Returns a `[Simulated]` access-request answer.      |
| `vpn_log_check`         | **Real**    | Reads sample log files via `/api/v1/logs/analyze`.  |
| `status_check`          | **Real**    | Queries the actual ticket DB for the session.       |

- Every simulated path is tagged `automation_simulated: true` in the
  API response, prefixed `[Simulated]` in the text, and shown as a chip
  in the chat UI.
- Ticket creation is **gated**: only on explicit user request, urgent
  language, critical severity / high urgency, automation failure, or
  weak KB match. Knowledge questions never open a ticket.

> Honesty about what's real vs. stubbed is itself a product feature.
> Hidden stubs lose the user's trust the first time they're discovered.

Deep dive: [`../README.md`](../README.md) "Simulated automations".

---

## Slide 8 — UX (Checkpoint 6)

- Calm enterprise UI — Inter + JetBrains Mono, neutral palette, two
  accents.
- Four surfaces: Chat / Tickets / Metrics / Sources.
- Chat surfaces **per-turn explainability**: match strength, sources,
  ticket id, escalation chip, simulated-automation chip, and a
  collapsible **Route Trace** strip with category, intent, severity,
  urgency, ticket reason, and automation status.
- Tickets table is built like ServiceNow / Jira (table + inline detail);
  destructive actions confirm.
- Metrics page maps 1:1 to product success metrics; turns amber/red on
  SLO breach.
- Sources page is a searchable, filterable browser of all 130 KB docs.

> The Route Trace strip is the unique UX move. Commercial products tell
> you the bot answered. We show you which agents fired and why.

Deep dive: [`UX.md`](UX.md) (full ASCII wireframes for every page).

---

## Slide 9 — MCP integration (Checkpoint 7)

- Real FastMCP server (`mcp_server/server.py`), stdio transport.
- Tools exposed: `create_ticket`, `list_tickets`, `update_ticket_status`,
  `update_ticket_priority`, `analyze_logs`, `recent_errors`.
- **Cross-transport parity test** (`make test-mcp`): MCP and HTTP
  both write to the same SQLite DB; mutations on one side are
  observable on the other. 5/5 steps pass.
- Live demo: VS Code Copilot Chat → `create_ticket` over MCP → ticket
  appears in the web Tickets page on refresh.
- Vendor-neutral: same protocol works for the official GitHub MCP
  server (appendix in `MCP_VSCode_Demo.md`).

> Without MCP, every new client we want to support would need to learn
> our HTTP shape, auth header, and JSON contract. With MCP, clients
> discover the tools at runtime. That's the standardisation point.

Deep dive: [`MCP_PROOF.md`](MCP_PROOF.md), [`MCP_VSCode_Demo.md`](MCP_VSCode_Demo.md).

---

## Slide 10 — Validation & testing (Checkpoint 8)

| Harness                   | Run command       | What it asserts                            |
| ------------------------- | ----------------- | ------------------------------------------ |
| Deterministic routing     | `make test`       | Every conditional edge in the orchestrator. **10/10 scenarios, 100 %** per-axis. |
| MCP cross-transport proof | `make test-mcp`   | MCP↔HTTP land in the same DB. **5/5 steps**.|
| Live-LLM accuracy         | `make test-llm`   | Claude classification quality on real text. **≥ 85 %** target. |

- The deterministic harness mocks the LLM-driven agents and the IT Ops
  client, then runs the **real** orchestrator and Workflow / Escalation
  agents against 10 scenarios that cover every routing branch.
- LangGraph captures node-action references at compile time, so the
  harness rebuilds the compiled graph after patching to wire the mocks
  in. (Details in `_run_scenario` docstring.)
- All three harnesses write timestamped JSON reports to
  `tests/results/`. The deterministic one also writes a Markdown
  summary, regenerated on every run.

> Splitting the deterministic and live-LLM harnesses is the key move:
> system regressions surface in the deterministic harness in <50 ms;
> classification regressions surface in the live-LLM harness on demand.
> CI runs the cheap one on every PR.

Deep dive: [`VALIDATION.md`](VALIDATION.md).

---

## Slide 11 — Industry context

| Capability                         | ServiceNow Now Assist | Zendesk AI | Freshservice Freddy | Moveworks | This capstone   |
| ---------------------------------- | :-------------------: | :--------: | :-----------------: | :-------: | :-------------: |
| Conversational LLM front door      |          ✅           |     ✅     |         ✅          |    ✅     |       ✅        |
| RAG with citations                 |          ✅           |     ✅     |    Limited          |    ✅     |       ✅        |
| Multi-agent routing                 |          ✅           |  Limited   |    Limited          |    ✅     |       ✅        |
| **Visible per-turn route trace**    |          ❌           |     ❌     |         ❌          |    ❌     |       ✅        |
| **Vendor-neutral tool protocol**    |          ❌           |     ❌     |         ❌          |    ❌     |  ✅ (MCP)       |
| **Deterministic open routing tests**|          ❌           |     ❌     |         ❌          |    ❌     |       ✅        |
| **Honest stub labelling**           |          ❌           |     ❌     |         ❌          |    ❌     |       ✅        |
| Out-of-the-box integrations        |          ✅           |     ✅     |         ✅          |    ✅     |   Stubbed       |
| Multi-tenant / RBAC                 |          ✅           |     ✅     |         ✅          |    ✅     |   Single-tenant |

> The trade-off is clear. We can't compete on integrations or
> multi-tenant. We *can* compete on auditability, openness, and
> standardised interoperability.

Deep dive: [`INDUSTRY_COMPARISON.md`](INDUSTRY_COMPARISON.md).

---

## Slide 12 — Live demo flow (~5 min)

1. `make dev` → ops API + backend + frontend up.
2. Open `http://localhost:5173`.
3. **Knowledge-only**: ask *"How do I clear my browser cache?"* — show
   citations + route `intake → knowledge → final_response`.
4. **Automation, simulated**: ask *"I forgot my password and need a
   reset link."* — show `[Simulated]` chip, route
   `intake → knowledge → workflow → final_response`.
5. **Urgent escalation**: ask *"VPN is down for the whole team and
   nobody can work."* — show ticket created + escalation chip + route
   `intake → knowledge → workflow → escalation → final_response`.
6. **Tickets page**: refresh; show the urgent ticket with priority
   `critical`. Open the detail panel; flip status to `resolved`.
7. **MCP**: in a second terminal, `make test-mcp`; show the JSON
   report and the matching Tickets-page row in the dev DB.

> If demo gods cooperate, also: open VS Code Copilot Chat with
> `.vscode/mcp.json` configured; ask *"Use the IT support tools to open
> a ticket: title 'demo', category software, priority low"*. Refresh
> the web Tickets page — the VS-Code-created ticket is right there.

---

## Slide 13 — What we'd build next

1. Real adapters for `password_reset`, `account_unlock`,
   `software_install` (Okta / Entra / Intune).
2. Ticket follow-up loop — second agent polls for resolution, pings
   user, closes when confirmed.
3. Move sessions to Redis, tickets to Postgres, dual-write to a
   warehouse for analytics.
4. Slack / Teams surface in addition to web chat.
5. Pilot rollout: 50 employees, 2 weeks, weekly metrics review.

> The architecture is set up so each of these is a localised change,
> not a re-platform. New adapters are intent-handlers; new surfaces
> share the same backend; new clients use the same MCP tools.

---

## Slide 14 — Risks & mitigations

| Risk                                                    | Mitigation                                                  |
| ------------------------------------------------------- | ----------------------------------------------------------- |
| LLM mis-classification triggers a wrong automation      | Workflow agent acts on **structured intake output**, not    |
|                                                         | raw LLM text. Automatable intents are an enum.              |
| KB doc instructs the model to bypass routing            | Knowledge agent's prompt cites docs but routing is decided  |
|                                                         | upstream by Intake's structured fields, not by KB text.     |
| Ops API offline → ticket loss                           | `it_ops_client.py` returns `LOCAL-...` fallback id; UI      |
|                                                         | shows banner; ticket is recorded locally and synced later.  |
| Single-tenant assumption breaks under multi-org demand  | Add tenant column + auth middleware; bounded change.        |
| Live-LLM costs balloon at scale                         | Haiku is the default; Sonnet/Opus are opt-in via env.       |
|                                                         | Caching common intake responses is phase-2 work.            |

---

## Slide 15 — Closing

- **Resolves the resolvable.** Knowledge questions get cited answers;
  automatable intents get safe stubs; everything else opens a ticket.
- **Escalates the rest cleanly.** Critical/urgent cases, weak KB
  matches, and explicit human asks all reach a real human with full
  context.
- **Auditable end-to-end.** Every assistant turn has a visible route
  trace. Every ticket has a `TicketEvent` and an `AuditLog` row.
- **Standardised at the edge.** MCP makes new clients free.
- **Tested deterministically.** Routing regressions surface in <50 ms.

> Thank you. Questions? — see also [`../README.md`](../README.md) for
> setup, [`PRODUCT.md`](PRODUCT.md) for the deeper product story, and
> [`VALIDATION.md`](VALIDATION.md) for the live test reports.

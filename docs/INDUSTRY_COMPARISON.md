# Industry comparison

Where does this project sit relative to commercial AI-assisted IT support
products? This doc is for the grader and for anyone who wants to know
whether the architecture choices match what enterprise vendors are
actually shipping in 2026.

We compare against four widely-deployed products:

- **ServiceNow Now Assist** (Virtual Agent + AI Search)
- **Zendesk AI** (Advanced AI add-on)
- **Freshservice Freddy AI** (Freddy Self-Service + Copilot)
- **Moveworks** (purpose-built AI agent for IT)

---

## 1. Capability matrix

| Capability                                              | ServiceNow Now Assist | Zendesk AI | Freshservice Freddy | Moveworks | **This capstone** |
| ------------------------------------------------------- | :-------------------: | :--------: | :-----------------: | :-------: | :---------------: |
| Conversational LLM front door                           |          ✅           |     ✅     |         ✅          |    ✅     |        ✅         |
| RAG over company knowledge base                         |          ✅           |     ✅     |         ✅          |    ✅     |        ✅         |
| Cited sources in answers                                |          ✅           |     ✅     |    Limited          |    ✅     |        ✅         |
| Routing to multiple specialised agents                  |          ✅           |  Limited   |    Limited          |    ✅     |        ✅         |
| Visible route trace per response                        |        ❌             |     ❌     |         ❌          |    ❌     |        ✅         |
| Native ticketing                                        |     ✅ (own ITSM)    |  ✅ (own)  |     ✅ (own)        | Integrates |        ✅         |
| Integrations to identity / asset systems                |        ✅             |     ✅     |         ✅          |    ✅     |  Stubbed (✓ shape)|
| Bring-your-own-LLM model                                |        ✅             |  Limited   |    Limited          |    ✅     |        ✅         |
| Vendor-neutral tool protocol (MCP-like)                 |        ❌             |     ❌     |         ❌          |    ❌     |        ✅ (MCP)   |
| Open-source / forkable                                  |        ❌             |     ❌     |         ❌          |    ❌     |        ✅         |
| Per-turn explainability (severity, urgency, intent)     |     Partial          |  Partial   |    Partial          |  Partial  |        ✅         |
| Deterministic routing tests                             |     Internal         |  Internal  |    Internal         |  Internal |        ✅ (open)  |
| Honest "simulated automation" labelling                 |     Hidden           |  Hidden    |    Hidden           |  Hidden   |        ✅         |

Sources:
- ServiceNow: <https://www.servicenow.com/products/now-assist.html>
- Zendesk AI: <https://www.zendesk.com/service/ai/>
- Freshservice Freddy: <https://www.freshworks.com/freshservice/freddy-ai/>
- Moveworks: <https://www.moveworks.com/us/en/platform>

(All accessed 2026-Q2; capabilities change quickly so treat the matrix
as a snapshot, not a deep audit.)

---

## 2. Where this project is different

### 2.1 Vendor-neutral tool protocol

The four commercial products are **closed ecosystems**. Their tools live
behind vendor APIs; integrations are paid connectors. If you want to use
ServiceNow's runbook automations from a different chat surface, you build
a custom integration.

This project uses **Model Context Protocol** as the integration boundary.
The same `create_ticket` / `analyze_logs` / `recent_errors` tools are
callable from VS Code, Claude Desktop, the LangGraph backend, or any
future MCP-aware client without any new code on either side. We
demonstrate the cross-transport claim with a deterministic test
(`tests/test_mcp_proof.py`) and a live demo path (`docs/MCP_VSCode_Demo.md`).

This is the single biggest architectural difference and the most
defensible product position for a small team: **interoperability beats
features when the buyer already owns three other tools.**

### 2.2 Visible route trace per response

ServiceNow, Zendesk, and Freshservice will tell you the bot answered
your question. Moveworks will tell you which "skill" handled it. None of
them will show you "intake → knowledge → workflow → escalation, with
this severity, this urgency, this ticket reason" inline in the chat
turn.

We do (`frontend/src/pages/ChatPage.jsx` `RouteTraceStrip`). It's
collapsible, so it doesn't clutter the end-user experience, but it
removes ambiguity for graders, compliance reviewers, and operators
debugging a regression.

### 2.3 Honest "simulated" labelling

Every commercial demo paints automations as production-grade. Most are
heavily scoped or hand-wired for the demo. We chose to be explicit:
the chat UI tags every stubbed automation with a chip and a
`[Simulated]` prefix in the response text, and the API exposes
`automation_simulated: true` so any downstream surface can do the same.

The intent is to model the **right interface** between the multi-agent
system and the rest of the IT platform. Replacing a stub with a real
adapter is a localised change in `backend/agents/workflow_agent.py`.

### 2.4 Deterministic, open routing tests

We ship a fully-mocked harness that exercises every conditional edge in
the LangGraph graph in <1 second, with no API spend, no Claude required.
That's a non-negotiable for CI on a small team. Commercial products
don't expose anything equivalent.

---

## 3. Where this project is weaker

### 3.1 Out-of-the-box integrations

ServiceNow, Zendesk, Freshservice, and Moveworks ship with hundreds of
production integrations (Okta, Entra, Slack, Teams, Jira, Salesforce,
…). This project ships **stubs** for every automation except VPN log
analysis and ticket status lookup. A pilot would need to write the real
adapters before deflecting real tickets.

Mitigation: the architecture is set up so each adapter is one new
intent-handler in `workflow_agent.py`. Real engineering hours to
production-grade Okta/Entra/Slack integrations: ~2–3 weeks for a single
engineer per adapter.

### 3.2 Multi-tenant story

The IT Ops API uses a single shared service token. There's no notion of
organisations, RBAC, or tenant isolation. Every commercial product has
this; we're a single-tenant capstone.

Mitigation: the boundaries are right (one secret, one DB, one origin
allowed via CORS). Adding a tenant column to `tickets` and an
auth middleware is a localised change.

### 3.3 No analytics / reporting suite

Commercial products ship dashboards, weekly reports, ROI calculators.
We expose `/metrics` and a small Metrics page. That's enough for an MVP
pilot, not enough for executive-tier reporting.

Mitigation: dual-writing tickets to a warehouse (BigQuery / Snowflake)
is a phase-2 task in [`PRODUCT.md`](PRODUCT.md).

### 3.4 Maturity / scale

We don't claim to handle 10k tickets / day. Sessions are in-process,
SQLite is single-writer, and the LangGraph agent runs synchronously.

Mitigation: the README's "Status" section says exactly this. Phase-2
scaling work (Redis sessions, Postgres tickets, async LangGraph) is
identified.

---

## 4. Positioning takeaway

If a buyer already has ServiceNow / Zendesk / Freshservice and wants
deeper AI assistance, the right answer is to enable the vendor's AI
add-on. They have the integrations and the data.

This project's positioning is different:

- A team **without** an existing ITSM vendor, or
- A team that already has one but wants AI assistance that lives in
  **multiple clients** (VS Code, Claude Desktop, the chat UI, future
  voice / Slack surfaces) without paying per-seat per surface, or
- A team that values **open, auditable routing** over a closed black box.

For those teams, the architecture in this capstone — multi-agent
LangGraph + grounded RAG + MCP as the integration boundary — is a viable
alternative.

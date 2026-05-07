# UX design — IT Support AI

This doc covers grading checkpoint **6 (UX design & user experience)**:
the wireframes, the design rationale, and the choices we made about what
to surface vs. hide. The implementation lives in `frontend/src/`.

---

## 1. Design principles

1. **Calm enterprise UI, not a demo toy.** End users compare this to
   Slack, Linear, and modern ITSM portals. Off-brand colours, gradient
   backgrounds, and joke icons would undercut trust. We use a single
   neutral palette, two accent colours, real type (Inter + JetBrains Mono),
   and avoid emoji in the product UI.
2. **One screen of cognition at a time.** The sidebar is a list of four
   surfaces (Chat, Tickets, Metrics, Sources). Each surface has one job.
   Switching tabs preserves chat state — a curious user can check the
   Tickets page mid-conversation and come back without losing context.
3. **Show the system's reasoning.** Match strength, route trace, ticket
   decision reason, automation status, and the simulated-automation flag
   are all visible per turn (collapsible by default). Compliance and
   demo grading both benefit; ordinary users can ignore them.
4. **Honest about limits.** Loading states, offline ops API, weak KB
   match, and "I'm a stub" automation all surface visually instead of
   being hidden. We'd rather lose a little polish than gaslight the
   user about what's real.
5. **Keyboard-first composer.** Enter sends, Shift+Enter not yet
   supported (single-line input is the simplest correct thing); the
   sidebar is mouse-driven but the chat itself is fully keyboard
   navigable (focus rings via `:focus-visible`, no `outline: none`
   without a replacement).

---

## 2. Wireframes (ASCII, faithful to the implementation)

### 2.1 Chat (default)

```
┌────────────────────────┬──────────────────────────────────────────────┐
│                        │  Support assistant                            │
│  ✦ IT Support          │  Ask about passwords, VPN, software errors…  │
│    AI assistant        ├──────────────────────────────────────────────┤
│                        │                                              │
│  WORKSPACE             │     ┌──────────────────────────────────┐     │
│  • Chat       (active) │     │ How do I clear my browser cache? │     │
│    Tickets             │     └──────────────────────────────────┘     │
│    Metrics             │                                              │
│    Sources             │  ✦ Support assistant   [kb match · strong]   │
│                        │  ┌──────────────────────────────────────┐    │
│                        │  │ 1. Open Settings → Privacy & ...     │    │
│                        │  │ 2. Click "Clear browsing data" ...   │    │
│                        │  │    Citation: [kb-014] Browser cache  │    │
│                        │  └──────────────────────────────────────┘    │
│                        │  ┌── Sources ────────────────────────────┐   │
│                        │  │ kb-014  Browser cache cleanup steps   │   │
│                        │  └───────────────────────────────────────┘   │
│                        │                                              │
│                        │  ▶ Route trace   intake → knowledge → final │
│                        │                                              │
│                        │                                  👍 👎      │
│                        │                                              │
│  ───────────────────   ├──────────────────────────────────────────────┤
│  ● All systems normal  │                                              │
│                        │  ┌──────────────────────────────────────┐    │
│  SESSION               │  │ Describe your IT issue…           Send│   │
│  a3b1c8e2…f9d4         │  └──────────────────────────────────────┘    │
│  [ New session ]       │  The assistant uses your KB + Claude.        │
└────────────────────────┴──────────────────────────────────────────────┘
```

What's surfaced and why:

| Surface element                | Reason                                                         |
| ------------------------------ | -------------------------------------------------------------- |
| Sidebar status pill            | Operators see ops-API/KB health at a glance.                   |
| Session id + "New session"     | Easy way to reset state during a demo or for a real user.      |
| `kb match · strong/weak`       | The user can tell when the answer is grounded vs. best-effort. |
| Sources block                  | Citations build trust. Click a doc id → Sources page deeplink. |
| Route-trace strip              | Default-collapsed; expandable. Grader / operator-facing.       |
| 👍 👎 buttons per assistant turn | Per-turn satisfaction; feeds the `/feedback` endpoint.         |
| `Simulated automation` chip    | Shown only when an automation is a stub. Honesty is the point. |

### 2.2 Chat (urgent VPN outage — fully traced)

```
✦ Support assistant   [kb match · strong]
┌───────────────────────────────────────────────────────────────────┐
│ 1. Confirm scope: is the outage limited to one region or global?  │
│ 2. Check VPN concentrator status …                                │
│ 3. Review network_events.log …                                    │
│ ────                                                              │
│ VPN log check completed: VPN authentication errors detected;     │
│ investigate ASAP.                                                 │
│ ────                                                              │
│ I could not resolve this confidently from the knowledge base, so │
│ I routed it to human IT support. Ticket TKT-1A2B3C4D has been    │
│ opened with priority critical. Expected response time: 2-4 hours. │
└───────────────────────────────────────────────────────────────────┘
[TKT-1A2B3C4D]   [Escalated]   [Simulated automation … no, this one is real]

▼ ROUTE TRACE  intake → knowledge → workflow → escalation → final_response
   nodes      intake → knowledge → workflow → escalation → final_response
   category   vpn
   intent     vpn_log_check
   severity   critical
   urgency    high
   ticket     urgent/escalation language detected
   automation success
```

This one screen sells the whole architecture: the user sees a real ticket,
a real escalation, a route trace they can audit, and the inputs intake
extracted. No backend access required.

### 2.3 Tickets

```
Tickets                                                     [ Refresh ]
All issues opened by the assistant or filed manually.
─────────────────────────────────────────────────────────────────────────
3 tickets
─────────────────────────────────────────────────────────────────────────
   TICKET ID    TITLE                       CATEGORY  PRIORITY  STATUS
▶  TKT-9F1A     VPN is down for the whole…  vpn       CRITICAL  ● escalated
▼  TKT-7B2C     Please create a ticket for… hardware  MEDIUM    ● open
       Description
       My laptop screen has a vertical pink line down the middle.
       Severity: medium  Urgency: medium  Session: 4f9a-…  Updated: today
       SET STATUS  [open]  [in progress]  [escalated]  [resolved]
       ─────────
       [ 🗑 Delete ticket ]
▶  TKT-3D5E     I forgot my password and …  password  LOW       ● resolved
```

Why it looks like this:

- Table-first layout: IT operators are used to ServiceNow / Jira tables.
- Inline expand-row instead of a separate detail page: faster scanning,
  no navigation churn.
- Status as colour + dot, not a select dropdown by default: read-first,
  edit on demand.
- Destructive actions confirm with a native dialog. We never auto-delete.

### 2.4 Metrics

```
System metrics                                              [ Refresh ]
Live snapshot of the assistant pipeline and dependencies.

┌─────────────────┐  ┌──────────────────┐  ┌──────────────┐
│ TOTAL REQUESTS  │  │ AVG RESPONSE TIME│  │ TOTAL TICKETS│
│       142       │  │     1840 ms      │  │      37      │
│                 │  │ Within target    │  │              │
└─────────────────┘  └──────────────────┘  └──────────────┘

┌─────────────────┐  ┌──────────────────┐  ┌──────────────┐
│ ESCALATIONS     │  │ KNOWLEDGE BASE   │  │ SYSTEM UPTIME│
│        3        │  │ Seeded           │  │  4h 12m 7s   │
│ Active human…   │  │ Ready for retrl. │  │ Ops API ok   │
└─────────────────┘  └──────────────────┘  └──────────────┘

┌─────────────────┐
│ USER SATISFACTION│
│      82%        │
│  41 up · 9 down │
└─────────────────┘
```

The cards map 1:1 to the success metrics in [`PRODUCT.md`](PRODUCT.md)
§2 so a manager opening this page can sanity-check pilot health without
needing a dashboard tool. Cards turn amber/red automatically when an
SLO breaches.

### 2.5 Sources

```
Knowledge sources                                          [ Refresh ]
All KB documents the assistant can cite. Loaded from it_support.json.

[ search: error 1603 ………………… ]   [all] [password] [network] [software] …
                                                       3 of 130 documents

┌─────────────────────────────────────────────────────────────────────┐
│ kb-003   Software installation error 1603        SOFTWARE  v2024-07 │
│          Software installation error 1603 indicates a fatal MSI…    │
└─────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────┐
│ kb-006   Windows error 0x80070005 (Access Denied) SOFTWARE v2024-05 │
│          Windows error 0x80070005 means Access Denied. It often…    │
└─────────────────────────────────────────────────────────────────────┘
```

Search across title / id / body, plus a category filter. Click expands
the full body inline. This page is what the IT documentation owner uses
to confirm what the assistant has access to today.

---

## 3. Component map (for the reader of `frontend/src/`)

```
frontend/src/
├── main.jsx              — Vite entry
├── App.jsx               — Layout, sidebar nav, opsHealth probe
├── hooks/useChat.js      — POST /chat, POST /feedback, message state
├── pages/
│   ├── ChatPage.jsx      — Chat surface, AssistantBubble, RouteTraceStrip
│   ├── TicketsPage.jsx   — Ticket table + inline detail panel
│   ├── MetricsPage.jsx   — Cards bound to /metrics
│   └── SourcesPage.jsx   — KB browser
└── (CSS variables in frontend/index.html — single source of truth)
```

The chat UI's `RouteTraceStrip` is the new addition for grading: it
shows the agents that actually ran, the inputs Intake extracted, and the
ticket / automation reasons — all from fields that are already on the
`/chat` API response. Implementation in `frontend/src/pages/ChatPage.jsx`.

---

## 4. Design decisions worth surfacing

### 4.1 Why we don't auto-create tickets for knowledge questions

A common product mistake is "every interaction → a ticket". That fills
the queue with answered questions and trains agents to ignore the queue.
Our `_should_create_ticket` (in `backend/agents/workflow_agent.py`) only
opens a ticket on:

- explicit user request ("please create a ticket"),
- urgent / escalation language,
- critical severity or high urgency,
- a failed automation,
- a weak / no KB match (so the human has something to follow up on).

In every other case we answer and leave no breadcrumbs in the queue.

### 4.2 Why we surface "kb match · weak" instead of pretending

A weak match is not a failure mode for the product — it's the assistant
saying "I'm guessing here, let me check in with you". Hiding that signal
would be paternalistic and dishonest. The chat UI puts a coloured chip
on the bubble (teal/amber/grey) and the agent's prompt is explicitly
the `NO_MATCH_PROMPT`, which ends with one specific check-in question.

### 4.3 Why simulated automations are visibly tagged

If a grader or pilot user thinks the password reset actually fired, two
things go wrong: trust collapses on first inspection, and product
priorities get distorted. The chip + `[Simulated]` prefix puts the
boundary between "demo logic" and "production adapter" right in the UI.
We use the `automation_simulated` boolean from the `/chat` response so
it stays a single source of truth.

### 4.4 Why the route trace is collapsed by default

End users don't care which agent fired. Operators, graders, and people
debugging a regression do. Default-collapsed `<details>` keeps both
audiences happy: zero visual noise for the end user, one click for the
expert. The trace is also assertion-tested (`tests/test_routing.py`),
so what the UI shows matches what the backend declares.

---

## 5. Accessibility & polish notes

- All interactive elements have visible focus rings (`:focus-visible`
  in `frontend/index.html`).
- Colour is always paired with text or icon (e.g. status uses dot +
  label, not colour alone) so colour-blind users are not penalised.
- The chat composer uses native `<input type="text">` so screen readers
  read it correctly. The Send button is keyboard-reachable.
- All buttons have `aria-label` when icon-only (👍 / 👎).
- The route-trace strip is a native `<details>`/`<summary>`, which is
  keyboard- and screen-reader-friendly out of the box.
- We avoid `outline: none` without replacement — the global stylesheet
  always provides a focus indicator.

---

## 6. What we'd build next (UX backlog)

1. Markdown rendering for fenced code blocks (currently inline-code only).
2. A "history" surface that lists past sessions for the same user once we
   wire identity in.
3. A keyboard shortcut palette (⌘K) for jumping between the four surfaces.
4. Optimistic ticket creation in the chat — show the ticket id immediately,
   then reconcile when the API returns.
5. A small "explain this trace" tooltip per route node so first-time users
   understand what `intake` / `knowledge` / `workflow` / `escalation` mean.

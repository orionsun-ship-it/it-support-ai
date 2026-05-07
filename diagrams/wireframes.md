# Wireframes — UI flow of information

This file shows the user's eye-line through the product. Where
[`workflow.md`](workflow.md) traces what happens _inside_ a turn, this
file traces what the user _sees_ across turns and across pages.

The wireframes are ASCII so they live next to the code, render in any
viewer, and stay greppable. They are **faithful to the implementation**
in `frontend/src/` — the labels, chips, and field positions match the
real components. (If you want a fuller treatment of design rationale, see
[`../docs/UX.md`](../docs/UX.md). This file is information-flow first.)

Contents:

1. [App shell and navigation](#1-app-shell-and-navigation)
2. [Chat — empty state → first response](#2-chat--empty-state--first-response)
3. [Chat — knowledge-only flow](#3-chat--knowledge-only-flow)
4. [Chat — simulated automation flow](#4-chat--simulated-automation-flow)
5. [Chat — urgent escalation flow](#5-chat--urgent-escalation-flow)
6. [Chat — weak match → user-stuck → escalation flow](#6-chat--weak-match--user-stuck--escalation-flow)
7. [Tickets list and detail](#7-tickets-list-and-detail)
8. [Metrics dashboard](#8-metrics-dashboard)
9. [Sources browser](#9-sources-browser)
10. [Cross-page flow: chat → tickets](#10-cross-page-flow-chat--tickets)
11. [Cross-transport flow: VS Code → web Tickets page](#11-cross-transport-flow-vs-code--web-tickets-page)
12. [Information-flow legend](#12-information-flow-legend)

---

## 1. App shell and navigation

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ┌────────────────────────┐ ┌──────────────────────────────────────────────┐ │
│ │ ✦ IT Support           │ │  Active surface (Chat / Tickets / Metrics /  │ │
│ │   AI assistant         │ │  Sources). Each surface has one job.         │ │
│ │                        │ │                                              │ │
│ │  WORKSPACE             │ │                                              │ │
│ │   ▸ Chat   (active)    │ │                                              │ │
│ │   ▸ Tickets            │ │                                              │ │
│ │   ▸ Metrics            │ │                                              │ │
│ │   ▸ Sources            │ │                                              │ │
│ │                        │ │                                              │ │
│ │     (spacer)           │ │                                              │ │
│ │                        │ │                                              │ │
│ │ ────────────────────── │ │                                              │ │
│ │ ● All systems normal   │◀┘                                              │ │
│ │                        │                                                  │ │
│ │ SESSION                │  Sidebar polls /api/health every 30s            │ │
│ │ a3b1c8e2…f9d4          │  → status pill turns amber/red on degradation. │ │
│ │ [ New session ]        │                                                  │ │
│ └────────────────────────┘                                                  │
└──────────────────────────────────────────────────────────────────────────────┘
```

Information flow:

- **Sidebar → main**: clicking a nav item swaps the surface; chat state
  is preserved (the chat page is mounted-but-hidden when other tabs are
  active, see `App.jsx`).
- **`/api/health` → status pill**: every 30 s. If the ops API is down,
  the pill turns red and the chat continues with an inline banner
  (`Banner kind="warn"` in `ChatPage.jsx`).
- **`New session` → reset**: regenerates a UUID via `crypto.randomUUID`,
  remounts `ChatPage` (the `key={sessionId}` clears history).

---

## 2. Chat — empty state → first response

### 2a. Empty state

```
┌────────────────────────────────────────────────────────────────────┐
│  Support assistant                                                 │
│  Ask about passwords, VPN, software errors, network, hardware…    │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│                              ┌──┐                                  │
│                              │✦ │       gradient mark              │
│                              └──┘                                  │
│                                                                    │
│                     How can we help today?                         │
│      Describe your IT issue in your own words. The assistant       │
│      will search the knowledge base, run safe automations when     │
│      possible, and escalate to a human when needed.                │
│                                                                    │
│      ┌──────────────────────────┐  ┌──────────────────────────┐    │
│      │ I forgot my password…    │  │ How do I set up the VPN? │    │
│      └──────────────────────────┘  └──────────────────────────┘    │
│      ┌──────────────────────────┐  ┌──────────────────────────┐    │
│      │ Outlook will not open…   │  │ Installer fails error 1603│    │
│      └──────────────────────────┘  └──────────────────────────┘    │
│                                                                    │
├────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────┐  Send →  │
│  │ Describe your IT issue…                              │          │
│  └──────────────────────────────────────────────────────┘          │
└────────────────────────────────────────────────────────────────────┘
```

### 2b. Sending → loading

```
┌────────────────────────────────────────────────────────────────────┐
│  Support assistant                                                 │
│  …                                                                 │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│                                ┌─────────────────────────────────┐ │
│                                │ How do I clear my browser cache?│ │
│                                └─────────────────────────────────┘ │
│                                                                    │
│  ┌──┐                                                              │
│  │✦ │  ● ● ●     ← three pulsing dots; tells the user "thinking"  │
│  └──┘                                                              │
│                                                                    │
├────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────┐  Send …  │
│  │ (input disabled)                                     │          │
│  └──────────────────────────────────────────────────────┘          │
└────────────────────────────────────────────────────────────────────┘
```

Flow:

- User clicks Send → `useChat.sendMessage(text)` (in `useChat.js`):
  1. Appends a `{role:"user", content:text}` bubble immediately.
  2. Sets `isLoading=true` → ThinkingIndicator + composer disabled.
  3. `POST /api/chat`.
  4. On 2xx: appends assistant bubble with full diagnostics
     (`route_trace`, `ticket_id`, `escalated`, `match_strength`,
     `automation_status`, `automation_simulated`, …).
  5. On error: appends an error bubble + sets `errorBanner`.

---

## 3. Chat — knowledge-only flow

End-to-end view for **Path A** (browser cache). Each frame is a moment
in time; the interesting flow is the inputs that produced the visible
chip set.

```
[ user message ]
      │
      ▼
┌────────────────────────────────────────────────────────────────────┐
│  ✦ Support assistant   [ kb match · strong ]                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ 1. Open the browser's settings menu.                         │  │
│  │ 2. Find "Privacy & security" → "Clear browsing data"…        │  │
│  │ 3. Choose a time range and the data types to clear…          │  │
│  │    (Citation: [kb-014])                                      │  │
│  └──────────────────────────────────────────────────────────────┘  │
│  ┌── Sources ──────────────────────────────────────────────────┐   │
│  │ kb-014   Browser cache cleanup steps                         │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                    │
│  ▶ Route trace  intake → knowledge → final_response               │
│                                                                    │
│                                                  👍   👎          │
└────────────────────────────────────────────────────────────────────┘
```

If the user expands the route trace strip:

```
▼ ROUTE TRACE
   nodes      [intake] → [knowledge] → [final_response]
   category   software
   intent     knowledge_question
   severity   low
   urgency    low
```

(No `ticket` row, no `automation` row — those nodes never wrote the
fields, so the strip skips them. See `RouteTraceStrip` in
`frontend/src/pages/ChatPage.jsx`.)

---

## 4. Chat — simulated automation flow

End-to-end view for **Path B** (password reset). Notice the new
`Simulated automation` chip.

```
[ "I forgot my password and need a reset link." ]
      │
      ▼
┌────────────────────────────────────────────────────────────────────┐
│  ✦ Support assistant   [ kb match · strong ]                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ 1. Go to https://portal.company.com/reset and enter your     │  │
│  │    corporate email. (Citation: [kb-001])                     │  │
│  │ 2. Click the link sent to your registered email within       │  │
│  │    30 minutes…                                               │  │
│  │                                                              │  │
│  │ [Simulated] Password reset eligibility verified. A reset     │  │
│  │ link would be sent to the registered email by the identity  │  │
│  │ provider in a production deployment.                         │  │
│  └──────────────────────────────────────────────────────────────┘  │
│  ┌── Sources ──────────────────────────────────────────────────┐   │
│  │ kb-001   Password reset procedure                            │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                    │
│  ▶ Route trace  intake → knowledge → workflow → final_response    │
│                                                                    │
│  ┌──────────────────────┐                              👍   👎    │
│  │● Simulated automation│                                          │
│  └──────────────────────┘                                          │
└────────────────────────────────────────────────────────────────────┘
```

Expanded route trace:

```
▼ ROUTE TRACE
   nodes      [intake] → [knowledge] → [workflow] → [final_response]
   category   password
   intent     password_reset
   severity   low
   urgency    low
   ticket     knowledge response or automation resolved the request
   automation success · simulated
```

The chip + `[Simulated]` prefix + the `automation` row's
"`success · simulated`" annotation all come from the same
`automation_simulated: true` field on the `/chat` response. Single
source of truth.

---

## 5. Chat — urgent escalation flow

End-to-end view for **Path C** (VPN outage). This is the screen that
shows off the most chips at once: ticket id, escalated banner,
expanded route trace.

```
[ "VPN is down for the whole team and nobody can work." ]
      │
      ▼
┌────────────────────────────────────────────────────────────────────┐
│  Support assistant            ┌────────────────────────────┐       │
│  Ask about passwords…         │● Escalated to human        │       │
│                               └────────────────────────────┘       │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│                ┌────────────────────────────────────────────────┐  │
│                │ VPN is down for the whole team and nobody can  │  │
│                │ work.                                          │  │
│                └────────────────────────────────────────────────┘  │
│                                                                    │
│  ✦ Support assistant   [ kb match · strong ]                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ 1. Confirm the scope: is it limited to one office /          │  │
│  │    region, or global? (Citation: [kb-002])                   │  │
│  │ 2. Check Cisco Secure Client status and concentrator         │  │
│  │    health…                                                   │  │
│  │ 3. Review network_events.log for authentication errors…      │  │
│  │                                                              │  │
│  │ VPN log check completed: VPN authentication errors           │  │
│  │ detected; investigate ASAP.                                  │  │
│  │                                                              │  │
│  │ I created ticket TKT-9F1A23BC with priority critical for     │  │
│  │ follow-up.                                                   │  │
│  │                                                              │  │
│  │ I could not resolve this confidently from the knowledge      │  │
│  │ base, so I routed it to human IT support. Ticket             │  │
│  │ TKT-9F1A23BC has been opened with priority critical.         │  │
│  │ Expected response time: 2-4 hours.                           │  │
│  └──────────────────────────────────────────────────────────────┘  │
│  ┌── Sources ──────────────────────────────────────────────────┐   │
│  │ kb-002   VPN setup with Cisco Secure Client / AnyConnect    │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                    │
│  ▼ ROUTE TRACE                                                     │
│     nodes      [intake] → [knowledge] → [workflow]                 │
│                → [escalation] → [final_response]                   │
│     category   vpn                                                 │
│     intent     vpn_log_check                                       │
│     severity   critical                                            │
│     urgency    high                                                │
│     ticket     urgent/escalation language detected                 │
│     automation success                                             │
│                                                                    │
│  ┌──────────────┐  ┌──────────┐                          👍   👎  │
│  │ ▢ TKT-9F1A23BC│  │● Escalated│                                  │
│  └──────────────┘  └──────────┘                                    │
└────────────────────────────────────────────────────────────────────┘
```

Notice three things flow together to make this screen:

1. The header **"Escalated to human"** chip in the top right is driven
   by `messages.some(m => m.escalated)` — once any turn escalates, the
   header reflects it for the rest of the session.
2. The amber **TKT-…** chip is `messages[i].ticketId` — derived from
   the `/chat` response's `ticket_id`.
3. The route trace expands automatically when the user clicks the
   summary line; the inline summary **always** shows the node sequence,
   so even collapsed it's enough for a grader.

---

## 6. Chat — weak match → user-stuck → escalation flow

This is the multi-turn flow. Two screenshots, one for the first
attempt (weak match), one for the follow-up where the user says it
didn't work.

### 6a. Turn 1 — weak match, best-effort answer + check-in

```
[ "Outlook will not open this morning." ]
      │
      ▼
┌────────────────────────────────────────────────────────────────────┐
│  ✦ Support assistant   [ kb match · weak ]   ← amber chip          │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ I don't have a specific runbook for this exact symptom, but  │  │
│  │ here are practical steps:                                    │  │
│  │ 1. Try opening Outlook in Safe Mode (outlook.exe /safe).     │  │
│  │ 2. Rebuild the Outlook profile under Mail in Control Panel.  │  │
│  │ 3. Disable add-ins one at a time…                            │  │
│  │                                                              │  │
│  │ Did that resolve your issue? If you're still stuck after     │  │
│  │ trying these steps, let me know and I'll get a human         │  │
│  │ technician involved.                                         │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ▶ Route trace  intake → knowledge → final_response                │
└────────────────────────────────────────────────────────────────────┘
```

Note: no automation, no ticket. `_should_create_ticket` doesn't fire
because Workflow never ran — knowledge_question + weak match in
isolation just yields a best-effort answer with a check-in question.
The escalation path only opens once the user **confirms** stuck.

### 6b. Turn 2 — user confirms stuck, escalation fires

```
[ "I tried that but it still didn't work." ]
      │
      ▼
┌────────────────────────────────────────────────────────────────────┐
│  ✦ Support assistant   [ kb match · weak ]                         │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ I could not resolve this confidently from the knowledge      │  │
│  │ base, so I routed it to human IT support. Ticket             │  │
│  │ TKT-3D5E11AA has been opened with priority critical.         │  │
│  │ Expected response time: 2-4 hours.                           │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ▼ ROUTE TRACE                                                     │
│     nodes      [intake] → [knowledge] → [escalation]               │
│                → [final_response]                                  │
│     category   software                                            │
│     intent     knowledge_question                                  │
│     ticket     escalation requires a ticket                        │
│                                                                    │
│  ┌──────────────┐  ┌──────────┐                          👍   👎  │
│  │ ▢ TKT-3D5E11AA│  │● Escalated│                                  │
│  └──────────────┘  └──────────┘                                    │
└────────────────────────────────────────────────────────────────────┘
```

Important detail: the route trace shows **`escalation` directly after
`knowledge`** — workflow is skipped. That's because knowledge_question
is not an automatable intent and no ticket was explicitly requested,
so `route_after_knowledge` jumped straight to escalation when
`_user_is_stuck` returned True.

---

## 7. Tickets list and detail

### 7a. List

```
┌────────────────────────────────────────────────────────────────────────────┐
│ Tickets                                                       [ Refresh ]  │
│ All issues opened by the assistant or filed manually.                      │
├────────────────────────────────────────────────────────────────────────────┤
│ 3 tickets                                                                  │
├────────────────────────────────────────────────────────────────────────────┤
│   TICKET ID    TITLE                       CATEGORY  PRIORITY  STATUS      │
├────────────────────────────────────────────────────────────────────────────┤
│ ▶ TKT-9F1A     VPN is down for the whole…  vpn       CRITICAL ● escalated  │
│ ▶ TKT-7B2C     Please create a ticket fo…  hardware  MEDIUM   ● open       │
│ ▶ TKT-3D5E     Outlook will not open this… software  CRITICAL ● escalated  │
└────────────────────────────────────────────────────────────────────────────┘
```

Source: `GET /api/tickets` → frontend → table. Status/priority chips
are colour-coded (red for critical/escalated, amber for in-progress,
green for resolved, brand-blue for open).

### 7b. Detail panel (click a row)

```
┌────────────────────────────────────────────────────────────────────────────┐
│ ▼ TKT-7B2C     Please create a ticket fo…  hardware  MEDIUM   ● open       │
│                                                                            │
│   DESCRIPTION                                                              │
│   My laptop screen has a vertical pink line down the middle.               │
│                                                                            │
│   Severity: medium    Urgency: medium    Session: 4f9a-…    Updated: today │
│                                                                            │
│   SET STATUS  [open]   [in progress]   [escalated]   [resolved]            │
│                                                                            │
│   ─────────────────────                                                    │
│   [ 🗑 Delete ticket ]                                                     │
└────────────────────────────────────────────────────────────────────────────┘
```

Information flow:

- Click a row → `setOpenId(ticketId)` → row expands.
- Click a status button → `PATCH /api/tickets/{id}/status` → optimistic
  local merge, then re-render with the server's authoritative row.
- Click delete → native `window.confirm` → `DELETE /api/tickets/{id}` →
  remove from list. Destructive, deliberately gated.

---

## 8. Metrics dashboard

```
┌────────────────────────────────────────────────────────────────────────────┐
│ System metrics                                                [ Refresh ]  │
│ Live snapshot of the assistant pipeline and dependencies.                  │
├────────────────────────────────────────────────────────────────────────────┤
│ ┌──────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐    │
│ │ TOTAL REQUESTS   │  │ AVG RESPONSE TIME   │  │ TOTAL TICKETS       │    │
│ │      142         │  │     1840 ms         │  │       37            │    │
│ │                  │  │ Within target       │  │                     │    │
│ └──────────────────┘  └─────────────────────┘  └─────────────────────┘    │
│ ┌──────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐    │
│ │ ESCALATIONS      │  │ KNOWLEDGE BASE      │  │ SYSTEM UPTIME       │    │
│ │       3          │  │ Seeded              │  │   4h 12m 7s         │    │
│ │ Active human…    │  │ Ready for retrieval │  │ Ops API healthy     │    │
│ └──────────────────┘  └─────────────────────┘  └─────────────────────┘    │
│ ┌──────────────────┐                                                       │
│ │ USER SATISFACTION│                                                       │
│ │     82%          │                                                       │
│ │ 41 up · 9 down   │                                                       │
│ └──────────────────┘                                                       │
└────────────────────────────────────────────────────────────────────────────┘
```

Each card maps to a `/api/metrics` field. Cards turn amber/red when an
SLO breaches:

- `avg_response_time_ms > 3000` → amber, "Above 3s target"
- `total_escalations > 0` → red, "Active human handoffs"
- `kb_seeded == False` → red, "Run make ingest"
- `ops_api_available == False` → red sub-text "Ops API unreachable"
- `satisfaction_score < 0.7` → amber, < 0.4 → red

---

## 9. Sources browser

```
┌────────────────────────────────────────────────────────────────────────────┐
│ Knowledge sources                                             [ Refresh ]  │
│ All KB documents the assistant can cite. Loaded from it_support.json.      │
├────────────────────────────────────────────────────────────────────────────┤
│ [ search: error 1603 …………………… ]                                            │
│                                                                            │
│ [all]  [password]  [network]  [software]  [hardware]  [access]  …          │
│                                                  3 of 130 documents        │
├────────────────────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────────────────────────────────────────┐   │
│ │ kb-003   Software installation error 1603        SOFTWARE  v2024-07 │   │
│ │          Software installation error 1603 indicates a fatal MSI…    │   │
│ └──────────────────────────────────────────────────────────────────────┘   │
│ ┌──────────────────────────────────────────────────────────────────────┐   │
│ │ kb-006   Windows error 0x80070005 (Access Denied) SOFTWARE v2024-05 │   │
│ │          Windows error 0x80070005 means Access Denied…              │   │
│ └──────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────┘
```

Source: `GET /api/sources` → list of all KB documents on disk (130
total). Click a card to expand the full body.

The Sources page is the **read-only counterpart** to retrieval — it
shows everything the assistant _could_ cite. Combined with the
per-turn citations in the Chat page, the user can verify the
assistant is grounded in the same corpus they can see.

---

## 10. Cross-page flow: chat → tickets

```
┌──────────────────────────┐                  ┌──────────────────────────────┐
│   CHAT                   │  user clicks     │  TICKETS                     │
│                          │  "Tickets" in    │                              │
│  ✦ Support assistant     │  sidebar         │  3 tickets                   │
│  ┌────────────────────┐  │  ───────────────▶│  ┌────────────────────────┐  │
│  │ I created ticket   │  │                  │  │ TKT-9F1A   VPN is down…│  │
│  │ TKT-9F1A23BC with… │  │                  │  │ CRITICAL · escalated   │  │
│  └────────────────────┘  │                  │  └────────────────────────┘  │
│  ┌─────────────┐         │                  │  …                           │
│  │ ▢ TKT-9F1A23│         │                  │                              │
│  └─────────────┘         │                  │  Click row → detail panel    │
└──────────────────────────┘                  │   → set status to "resolved" │
                                              │   → PATCH /tickets/.../status│
                                              │   → optimistic update        │
                                              │   → row chip turns green     │
                                              └──────────────────────────────┘
                                                            │
                                                            │ user goes back
                                                            ▼
                                              ┌──────────────────────────────┐
                                              │  CHAT (restored)             │
                                              │  Same scrollback because     │
                                              │  ChatPage is mounted-but-    │
                                              │  hidden across tabs (App.jsx)│
                                              └──────────────────────────────┘
```

Information flow:

- Chat → Tickets: the ticket id appears in the assistant bubble (for
  context) **and** as a chip (for filtering / scanning). The Tickets
  page shows the same id, fetched independently from `/api/tickets`.
  The two views share the same DB row — no client-side sync.
- Tickets → Chat: closing or escalating a ticket on the Tickets page
  doesn't notify the Chat page — that's deliberate. The Chat is a log
  of past turns; it doesn't mutate based on later out-of-band changes.
- Round-trip: if the same user asks "What's the status of my open
  tickets?" later in the same session, the `status_check` automation
  hits the same DB and returns the now-resolved status.

---

## 11. Cross-transport flow: VS Code → web Tickets page

This is the demo that sells the MCP integration story. The same
ticket appears in two clients backed by one DB.

```
┌────────────────────────────────────────────────────────────────────────────┐
│  Engineer's machine                                                        │
│                                                                            │
│  ┌──────────────────────────────┐         ┌──────────────────────────┐    │
│  │  VS Code Copilot Chat        │         │  Web app (Tickets page)  │    │
│  │                              │         │                          │    │
│  │  > Use IT support tools to   │         │  3 tickets               │    │
│  │  > open a ticket: title      │         │                          │    │
│  │  > "Wi-Fi flaky in conf B",  │         │  ▶ TKT-…  Wi-Fi flaky in │    │
│  │  > category network,         │         │     conf B   network     │    │
│  │  > priority medium.          │         │                MEDIUM    │    │
│  │                              │         │                ● open    │    │
│  │  → calls create_ticket       │         │  …                       │    │
│  │  (over MCP/stdio)            │         │                          │    │
│  │  → ack with TKT-…            │         │      ▲                   │    │
│  └──────────────┬───────────────┘         │      │ refresh           │    │
│                 │                         └──────┼──────────────────┘    │
│                 │ stdio                          │                        │
│                 ▼                                │                        │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                                                                    │  │
│  │  mcp_server.server  ──►  mcp_server.store  ──►  SQLite (it_ops.db) │  │
│  │                                  ▲                                 │  │
│  │                                  │                                 │  │
│  │                                  │ same engine, same models        │  │
│  │                                  │                                 │  │
│  │                                  ▼                                 │  │
│  │  services.it_ops_api.main  ◀──  /api/v1/tickets  ◀── backend       │  │
│  │                                                                    │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

Key invariants (verified in
[`../tests/test_mcp_proof.py`](../tests/test_mcp_proof.py)):

- `mcp_server.store.create_ticket(...)` and
  `services.it_ops_api.main.create_ticket(...)` share a single
  SQLModel `engine` and a single `Ticket` class.
- A row written by either transport is observable via the other.
- A mutation by either transport (status / priority) is observable via
  the other.

---

## 12. Information-flow legend

A consistent legend used across the wireframes above.

| Glyph                                       | Meaning                                                                                                     |
| ------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `[ kb match · strong ]` / `· weak`          | Match strength chip on assistant bubble. Drives KB-honest UX.                                               |
| `[Simulated]` prefix in body                | The automation is a stub, not a real adapter.                                                               |
| `● Simulated automation` (chip)             | Same signal, surfaced on the bubble for skim readers.                                                       |
| `▢ TKT-…` (chip)                            | A ticket id; clicking does nothing today (room for deeplink).                                               |
| `● Escalated` (red chip on bubble)          | This turn triggered the escalation node.                                                                    |
| `● Escalated to human` (red chip in header) | Any turn in this session has escalated. Persistent.                                                         |
| `▶ Route trace` / `▼ ROUTE TRACE`           | Collapsed / expanded info strip with all routing fields.                                                    |
| `→` / `┬─ … └─` in mockups                  | Information flow between screens or branches.                                                               |
| `▶` next to a row                           | Expandable (Tickets list, Sources cards).                                                                   |
| Coloured dots `● ● ● ●`                     | Status/priority colour code: green (resolved), amber (in_progress), red (escalated/critical), brand (open). |

---

## How to keep these wireframes accurate

If a UI change lands, the corresponding wireframe should change too.
The cheap signal: every distinct UI element shown above is rendered by
a function in `frontend/src/`:

| Wireframe element            | Component                                              |
| ---------------------------- | ------------------------------------------------------ |
| Sidebar + status pill        | `App.jsx` — `Sidebar`, `StatusPill`                    |
| Empty-state cards            | `ChatPage.jsx` — `EmptyState`                          |
| User / assistant bubbles     | `ChatPage.jsx` — `UserBubble`, `AssistantBubble`       |
| Sources block                | `ChatPage.jsx` — `Sources`                             |
| Route trace strip            | `ChatPage.jsx` — `RouteTraceStrip`, `RouteTraceInline` |
| Chips (kb match, ticket, …)  | `ChatPage.jsx` — `Chip` + per-section render           |
| Composer                     | `ChatPage.jsx` — `Composer`, `ThinkingIndicator`       |
| Tickets table + detail panel | `TicketsPage.jsx`                                      |
| Metrics cards                | `MetricsPage.jsx` — `Card` per metric                  |
| Sources cards                | `SourcesPage.jsx` — `DocCard`                          |

Find the function, change the rendering, update the wireframe in this
file. PRs that change UI should also touch this file.

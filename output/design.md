# Campus Customs Back-Office Desk: Design

The dashboard (`frontend/`, React + Vite + TypeScript) is the desk where a manager sits with the agent team. It's built to be **watched while the agents work** and **trusted when money moves**. The look is late-shift back office: near-black room, hot-pink neon sign, paper on the desk. Every design choice below serves one of three jobs:
1. show who is doing what right now;
2. make the human's decisions unmistakable;
3. make finished work feel finished.

Screenshots from the live test runs are in `output/design_images/`.

Run it:

```bash
cd frontend
npm run dev
```

It opens at `http://localhost:5173` and talks to the backend at `http://localhost:8000` (`VITE_API_URL`). The backend allows that origin in CORS.

---

## Layout: a three-column desk

```
┌──────────── neon sign · desk date · clock · backend status · Fresh start ────────────┐
│ TICKET SPIKE     │              THE FLOOR (live)                │  CHECKING (register) │
│  #101 stub       │   Inventory ─────────── Accounting           │  $3,400.00  + receipt│
│  #102 stub       │            \   BOSS   /                      │──────────────────────│
│  #103 stub       │   Facilities ───────── Customer Service      │  NEEDS YOUR SIGNATURE│
│  [Hand it to     │──────────────────────────────────────────────│  cheque(s)           │
│   the Boss →]    │  THE WIRE  |  SHIFT REPORT                   │──────────────────────│
│                  │  live event log / per-agent write-ups        │  TICKET FILE (notes) │
└──────────────────┴──────────────────────────────────────────────┴──────────────────────┘
```

The columns follow how a manager actually works:
- **Left: the work.** Tickets wait on a "ticket spike". You pick one and hand it to the Boss.
- **Center: the team.** You watch them work it.
- **Right: the money and the record.** You sign what needs signing and read the paper trail.

The rail and the right column are sticky, so the cash and pending signatures never scroll out of view while you read a long report. Below 1280px the right column drops under the floor as a row of cards. Below 860px everything stacks.

## The ticket spike (left)

- **Paper stubs.** Each ticket is a paper stub with a punched hole, a big pink ticket number, a type icon (👕 order, 🏠 rent, 🏷️ price override), the requester, and a perforated tear line above its database status. Picking one slides it out from the stack with a pink edge, and the **Hand it to the Boss →** button appears inside it. That phrasing says what really happens: the Boss decides who works it.
- **Rubber stamps for state.** State is shown with stamps, not just labels. Each stamp is rotated, outlined and in its own color:
  - **ON IT…** in blue while the team works;
  - **SIGN HERE** in amber, with a small wiggle, when a cheque for that ticket is waiting;
  - **RESOLVED** in pink.

## The floor (center top): how agents read differently

The five agents sit at desks on a grid floor, with **the Boss in the middle** and the four specialists in the corners. That's the real shape of the team: everything starts at the Boss, but any desk can reach any other.

**Each agent has its own color, glyph and voice:**

| Agent | Color | Glyph | Idle line |
|---|---|---|---|
| Boss | hot pink (the brand color, because the Boss speaks for the shop) | ★ | "Waiting for a ticket" |
| Inventory | amber | ▦ | "Stockroom quiet" |
| Accounting | mint | $ | "Ledger closed" |
| Facilities | violet | ⌂ | "Keys on the hook" |
| Customer Service | sky blue | ✉ | "Inbox clear" |

That color follows the agent everywhere: desk border, avatar, wire lines, feed rows, report cards and hand-off chips. After one run you can tell who is speaking without reading a name. The Boss's desk is larger with an uppercase name, so the manager's voice reads as the lead.

**Live state on each desk:**
- **Desk lamp.** It glows and pulses in the agent's color while they work, sits steady when done, and turns red if they failed. Idle desks are dimmed to half opacity, so the agents on this ticket stand out.
- **Speech bubble.** It shows what the agent is doing right now in plain English, with a blinking cursor while active. The API's raw tool names are translated: `check_stock` → "Checking the shelf…", `get_invoice` → "Pulling the invoice…", `delegate` → "Handing to Accounting: …". Above it, a small mono caption names the current action ("CHECKING THE SHELF", or "HANDING OFF ×3" when the Boss sends three tasks at once).
- **Footer.** It shows who handed them the work ("via Boss", "via Accounting"), the step count, the agent's final status pill, and a red **guardrail ×n** pill if a code guardrail blocked one of its calls.

**Hand-offs as live wires:**
- **Full connectivity:** faint dashed lines join every pair of desks (all 10 connections).
- **Active hand-off:** when an agent delegates, that line lights up in the delegator's color with dashes flowing toward the teammate.
- **Finished hand-off:** the wire stays solid once the hand-off is done.

In the ticket 103 test, the line between Accounting and Inventory lit up because Accounting asked Inventory directly, not through the Boss. The board makes that peer-to-peer hand-off visible.

## The wire and the shift report (center bottom)

**The wire** is the live log of every audit-trail step, polled every 1.5 s while a run is going. Each row has:
- a 24-hour timestamp;
- the agent's glyph and name in their color;
- what happened: which agent picked up the task, tool calls as mono chips with their arguments, results as ✓ / ! / ⛔ chips, and hand-offs as colored "➜ Inventory" chips.

Rows are **indented by delegation depth**, so Boss → Accounting → Inventory reads as a nested conversation. The panel scrolls itself to the newest line, and only the panel scrolls, never the whole page.

**The shift report** opens automatically when the run ends. Its tab shows a pink "ready" badge.

| Part | What it shows |
|---|---|
| **The Boss's call** | The decision in large type, with the status pill and stats: agents used, time on the floor, hand-offs, tool calls, tokens. |
| **One card per agent who worked** | Their own summary, the teammates they handed to, and the MCP tools they used, topped with their color. |
| **"Not needed on this ticket"** | The agents who stayed out, which is a deliberate reminder that good routing is lean. |
| **Facts the decision rests on** | Each fact with its source tool as a tag. |
| **The customer reply** | A cream paper letter with ruled lines and a pink **DRAFT · NOT SENT** stamp, because agents never send anything. |
| **Next up** | Who does what next. |

## Cash and approvals (right)

**The register.** Checking is shown as a register display: big glowing pink LED digits on black.
- **Payment.** When a payment is approved, the number **counts down** to the new balance over about 1.4 s, the display gives two small jolts, and a new line prints onto a **paper receipt** below ("#1 rent 1 −$2,400.00 · signed Test Owner").
- **Low cash.** If the balance falls below the $500 cushion, the LED turns red and "Below $500 cushion" pulses. Cash state is something you feel, not something you have to read.

**Needs your signature.** A payment the agents prepared arrives as a **cheque**:
- "Pay to the order of **Elm City Properties**" in handwriting;
- the amount in a box and **in words** ("Two thousand four hundred and 00/100 dollars");
- a memo with what it's for and which agent prepared it;
- the agent's reasoning, and the balance after paying (red if it breaks the cushion);
- a signature line where you **type your name**, which renders in handwriting, and the button **Approve & pay $2,400.00**.

The fine print says it plainly: *Agents only prepare payments. Your signature is what moves the money.* The counter next to the heading turns amber and pulses whenever a cheque is waiting.

**After signing:**
- the cheque disappears;
- the register counts down and the receipt prints;
- the ticket's stub gets a **RESOLVED** stamp, which slams on with a scale-down "thunk";
- the Boss's verdict gains a green **✓ Signed by Test Owner: $2,400.00 paid** line, and its pill flips to **Signed & paid**.

**Ticket file.** The selected ticket's record is a stack of **sticky notes**:
- the original request on blue;
- each agent's or human's signed note on alternating yellow and pink, slightly rotated, with the author in handwriting.

It's the audit trail a person would actually read.

## How resolved tickets show up

A ticket is marked resolved by the backend at the moment it's truly done:
- **No payment involved** (e.g. 103): resolved as soon as the run finishes.
- **A payment is needed** (e.g. 101, 102): resolved the moment the human signs, never before. This way the board can't hide money that still needs a decision.

On the board, a resolved ticket shows:
- the pink **RESOLVED** rubber stamp, which drops in with a "thunk" when it happens live;
- a database status tag of `resolved`;
- a slightly faded stub and a lower open count;
- a toast: "Ticket #103: the team is done. Marked resolved."

## Small touches that make it a place, not a page

- **Neon sign.** "Campus Customs" glows like a shop sign and flickers now and then.
- **Header context:** the desk date (Mon, Aug 31, 2026) from the database next to a real wall clock, and a green "Backend connected" dot that turns red with the URL if the API is down.
- **Fresh start.** The button resets the database. It asks twice ("Click again to reset" turns red) and is disabled while a run is going.
- **Signer memory:** your signature name is remembered between cheques.
- **Readable at a glance:** a mono font for numbers and tools, a grotesk for reading, and handwriting only for human marks (signatures, note authors, the letter sign-off). Handwriting always means a person was involved.
- **Accessibility:** tabs are real tabs, stubs work with the keyboard, the register is `aria-live`, and all motion turns off for `prefers-reduced-motion`.

## Why this design

- **Watching agents should feel like watching a team, not reading logs.** Spatial desks, colored voices and lit wires turn an abstract multi-agent run into something you can follow from across the room: Boss lights up, hands to Inventory, the wire glows amber, Inventory's lamp pulses, then the report appears.
- **Money needs ceremony.** A cheque with the amount in words, a typed signature and a visible balance-after makes a human slow down for exactly one second before paying, which is the right amount of friction for real money. The register's count-down and printed receipt confirm what happened without a page refresh.
- **Paper metaphors carry trust.** Stubs, stamps, receipts, sticky notes and a draft letter are things a shop manager already trusts. They make the agents' work look like work done in the shop, with a paper trail.
- **Black and pink with a color per agent.** The pink keeps the course's black-and-pink style and marks the brand, the Boss and the human's actions. Each specialist's color is bright enough on black to read at a glance and distinct from the others.

## Tested in a real browser

Tested with Playwright on Chromium at 1600×1000, against the live backend and `gpt-6-luna`. There were no console errors.

| Test | What we saw |
|---|---|
| Ticket 102 | Live floor (Boss → Facilities, Boss → Accounting), a cheque for $2,400, sign as "Test Owner", register $3,400 → $1,000, receipt printed, RESOLVED stamp. |
| Ticket 103 | Live floor (Boss → Inventory and Accounting, Accounting → Inventory, Boss → Customer Service), no cheque, auto-resolved on finish, shift report with the draft letter. |

The test runs were reset afterward, so the working database is back to its original values.

| Screenshot | Shows |
|---|---|
| `design_images/live_floor.png` | Ticket 103 mid-run: lit desks, the Accounting → Inventory wire, the live wire log |
| `design_images/cheque.png` | Ticket 102 finished, with the cheque waiting and the shift report |
| `design_images/after_payment.png` | After signing: register at $1,000, receipt line, RESOLVED stamp |
| `design_images/shift_report.png` | Ticket 103's shift report: verdict, crew cards, facts, draft letter |

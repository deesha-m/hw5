# Campus Customs Back-Office Desk: Design

The dashboard (`frontend/`, React + Vite + TypeScript) is the desk where a manager sits with the agent team. It's built to be **watched while the agents work** and **trusted when money moves**.

Its look follows the Campus Customs storefront from Homework 4, made more minimal for a back office: **ivory paper, ink, hairline rules and Yale Blue**. A shopper who saw the HW4 site and a manager at this desk should feel they're in the same shop: one in the front of house, one in the back office.

Every design choice below serves one of three jobs:
1. show who is doing what right now;
2. make the human's decisions unmistakable;
3. make finished work feel finished.

Screenshots are in `output/design_images/`.

Run it:

```bash
cd frontend
npm run dev
```

It opens at `http://localhost:5173` and talks to the backend at `http://localhost:8000` (`VITE_API_URL`). The backend allows that origin in CORS.

---

## The visual language (shared with the HW4 storefront)

| Element | Choice | Why |
|---|---|---|
| **Color** | Warm ivory paper (`#F5F1E8`) with near-white cards. Ink text (`#1B1A17`). **Yale Blue (`#00356B`) is the one brand accent:** the seal, the wordmark, buttons, the selected ticket, tabs, the Boss and the RESOLVED stamp. Brick (`#8C3B2C`) only means "attention" (low cash, money out, a cheque to sign). Brass appears only as a hairline on ticket notes. | Same palette as the HW4 shop, so the brand carries through. With one accent, there's never a question about what's clickable or what matters. Red-ish brick is reserved for money and risk, so it stays meaningful. |
| **Type** | **Cormorant Garamond** for names and big numbers (wordmark, ticket titles, agent names, the balance, payees). **Source Serif 4** for long, number-heavy text (the Boss's verdict, the customer letter). **Inter Light** for interface text. **IBM Plex Mono** for data (ticket numbers, tool calls, timestamps, statuses). **Caveat** handwriting only where a person signs or writes. | Each font has one job, the same system as HW4, so the page reads as name → number → detail. Cormorant only has old-style figures, so sentences full of dates and dollar amounts use Source Serif 4, whose figures are even. Handwriting always means a human was involved. |
| **Minimal, technical feel** | 1px hairline borders, 4px corners, no glows or heavy shadows, generous white space, uppercase micro-labels with wide letter-spacing, and a faint Yale Blue dot grid behind the agent floor. | It's a calm, modern tool that's easy to scan for a long shift. The dot grid quietly says "this is a map", and the agent cards sit on it like pins. |
| **Seal** | A Yale Blue "CC" seal with a thin ivory inner ring next to the serif wordmark "Campus Customs", above "BACK OFFICE · CHAPEL STREET". The favicon is the same seal. | It's the HW4 brass "CC" seal translated into Yale Blue: recognizably the same shop, in the back-office uniform. |

## Layout: a three-column desk

```
┌─ (CC) Campus Customs · desk date · clock · backend status ················ Fresh start ─┐
│ TICKET SPIKE     │              THE FLOOR (live)                │  CHECKING  $3,400.00  │
│  #101 card       │   Inventory ─────────── Accounting           │  paid-out ledger      │
│  #102 card       │            \   BOSS   /                      │───────────────────────│
│  #103 card       │   Facilities ───────── Customer Service      │  NEEDS YOUR SIGNATURE │
│  [Hand it to     │──────────────────────────────────────────────│  cheque(s)            │
│   the Boss →]    │  The wire  |  Shift report                   │───────────────────────│
│                  │  live event log / per-agent write-ups        │  TICKET FILE (notes)  │
└──────────────────┴──────────────────────────────────────────────┴───────────────────────┘
```

The columns follow how a manager works:
- **Left: the work.** Tickets wait on the spike. You pick one and hand it to the Boss.
- **Center: the team.** You watch them work it.
- **Right: the money and the record.** You sign what needs signing and read the paper trail.

The rail and the right column are sticky, so cash and pending signatures never scroll away while you read a long report. Below 1280px the right column drops under the floor. Below 860px everything stacks.

## The ticket spike (left)

- **Index cards.** Each ticket is a clean index card: a mono `#101` in Yale Blue, an uppercase type label (👕 customer order, 🏠 rent notice, 🏷️ price override), the subject in Cormorant, the requester, a hairline rule and the database status tag.
- **Selection.** Selecting a card gives it a Yale Blue border and an inner left rule, and the solid Yale Blue **Hand it to the Boss →** button appears inside it.
- **Stamps.** State is shown with small, rotated, outlined stamps in mono caps:
  - **ON IT…** in Yale light blue, pulsing while the team works;
  - **SIGN HERE** in brick, with a gentle nudge, when a cheque is waiting;
  - **RESOLVED** in Yale Blue.

## The floor (center top): how agents read differently

The five agents sit at desks on a dotted floor plan, with **the Boss in the middle** and the four specialists in the corners. That's the real shape of the team: everything starts at the Boss, but any desk can reach any other.

**Each agent has its own color and glyph, all from the same restrained palette:**

| Agent | Color | Glyph | Idle line |
|---|---|---|---|
| Boss | Yale Blue `#00356B` (a filled navy avatar, like the seal) | ★ | "Waiting for a ticket" |
| Inventory | brass `#93703E` | ▦ | "Stockroom quiet" |
| Accounting | ledger green `#2F7D5B` | $ | "Ledger closed" |
| Facilities | brick `#8C3B2C` (the Broadway building) | ⌂ | "Keys on the hook" |
| Customer Service | Yale light blue `#286DC0` | ✉ | "Inbox clear" |

All five colors are dark enough for small text on white. Each agent's color follows it everywhere: the colored rule on the left edge of its desk card, its name, its avatar ring, its wires, its rows in the wire, its shift-report card and its hand-off chips. After one run you can tell who's speaking without reading a name. The Boss alone has a filled navy avatar and a larger serif name, so the manager's voice reads as the lead.

**Live state on each desk:**
- **Status dot and card.** A small dot pulses in the agent's color while it works. The whole card gets a border and a soft shadow in that color. Idle desks fade to half opacity, so the agents on this ticket stand out.
- **Speech bubble.** It shows what the agent is doing right now in plain English, with a blinking cursor while active. Tool names are translated (`check_stock` → "Checking the shelf…", `delegate` → "Handing to Accounting: …"). Above it, a small mono caption names the current action ("CHECKING THE SHELF", or "HANDING OFF ×3" when the Boss sends three tasks at once).
- **Footer.** It shows who handed the work over ("via Boss"), the step count, the final status pill, and a **guardrail ×n** pill if a code guardrail blocked a call.

**Hand-offs as wires:**
- **Full connectivity:** faint dotted lines join every pair of desks (all 10 connections).
- **Active hand-off:** when an agent delegates, that line draws in the delegator's color with dashes flowing toward the teammate.
- **Finished hand-off:** it stays as a solid line once done.

In the ticket 103 run, the line between Accounting and Inventory lit up because Accounting asked Inventory directly, a peer-to-peer hand-off you can see on the floor.

## The wire and the shift report (center bottom)

Two underlined tabs, with the active one in Yale Blue.

**The wire** is the live log of every audit-trail step, polled every 1.5 s during a run. Each row has:
- a mono 24-hour timestamp;
- the agent's glyph and name in its color;
- what happened: the task picked up, tool calls as mono chips with arguments, ✓ / ! / ⛔ result chips, and colored "→ Inventory" hand-off chips.

Rows are **indented by delegation depth**, so Boss → Accounting → Inventory reads as a nested conversation, and the panel (only the panel) scrolls to the newest line.

**The shift report** opens automatically when a run ends. Its tab shows a Yale Blue "ready" badge.

| Part | What it shows |
|---|---|
| **The Boss's call** | The decision in Source Serif with a Yale Blue rule on the left, a status pill, and stats: agents used, time on the floor, hand-offs, tool calls, tokens. |
| **One card per agent who worked** | A top rule in the agent's color, its summary, its hand-offs and its MCP tools. |
| **"Not needed on this ticket"** | The agents who stayed out, which is a reminder that good routing is lean. |
| **Facts the decision rests on** | Each fact with its source tool as a small mono tag. |
| **The customer reply** | A letter on faintly ruled ivory paper with a brick **DRAFT · NOT SENT** stamp, because agents never send anything, signed "— The Campus Customs team" in navy handwriting. |
| **Next up** | Who does what next. |

## Cash and approvals (right)

**Checking.** The balance is the biggest number on the page: **$3,400.00** in Cormorant, in Yale Blue.
- **Payment.** When a payment is approved, the number counts down to the new balance over about 1.4 s, and a new line slides into the **Paid out** ledger below it ("#1 invoice 501 −$840.00 · signed Deesha Malpure").
- **Low cash.** Below the $500 cushion, the balance turns **brick red** and the label reads "Below $500 cushion". You notice the cash state without reading anything.

**Needs your signature.** A payment the agents prepared arrives as a **cheque** on white security-pattern paper (fine Yale Blue diagonal lines):
- "Pay to the order of **Elm City Properties**" in Cormorant;
- the amount in a navy box and **in words** in italic serif ("Two thousand four hundred and 00/100 dollars");
- a memo with what it's for and which agent prepared it;
- the agent's reasoning, and the balance after paying (brick if it breaks the cushion);
- a signature line where your typed name renders in navy handwriting, and the **Approve & pay $2,400.00** button.

The fine print says it plainly: *Agents only prepare payments. Your signature is what moves the money.* The count next to the heading turns brick whenever a cheque is waiting.

**After signing:**
- the cheque disappears;
- the balance counts down and the ledger line appears;
- the ticket card gets a Yale Blue **RESOLVED** stamp, which settles in with a short scale-down;
- the Boss's verdict gains a green "✓ Signed by *Deesha Malpure*: $2,400.00 paid" line, and its pill flips to **Signed & paid**.

**Ticket file.** The selected ticket's record:
- the original request on a pale Yale Blue note with a navy edge;
- each agent's or human's signed note on ivory with a brass edge, and the author in handwriting.

It's the paper trail a person would actually read.

## How resolved tickets show up

A ticket is marked resolved by the backend at the moment it's truly done:
- **No payment involved** (e.g. 103): resolved as soon as the run finishes.
- **A payment is needed** (e.g. 101, 102): resolved the moment the human signs, never before. This way the board can't hide money that still needs a decision.

On the board, a resolved ticket shows:
- the Yale Blue **RESOLVED** stamp;
- a `resolved` status tag;
- a slightly lighter title and a lower open count;
- a navy toast: "Ticket #103: the team is done. Marked resolved."

## Small touches that make it a place, not a page

- **Header context:** the desk date from the database (Mon, Aug 31, 2026) next to a live wall clock, and a green "Backend connected" dot that turns brick, with the URL, if the API is down.
- **Fresh start.** It resets the database. It asks twice ("Click again to reset" turns brick) and is disabled while a run is going.
- **Signer memory:** your signature name is remembered between cheques.
- **Accessibility:** tabs are real tabs, ticket cards work from the keyboard, the balance is `aria-live`, focus rings are Yale Blue, and all motion turns off for `prefers-reduced-motion`.

## Why this design

- **One brand, front and back.** Reusing the HW4 storefront's paper, ink, Yale Blue, seal and type system makes the back office feel like part of the same shop. A manager who knows the storefront recognizes this immediately.
- **Minimal so the agents are the color.** The chrome is neutral (ivory, hairlines, one navy accent), so the only saturated things on screen are the agents at work and the money. Your eye goes to the lit desk, the moving wire, the cheque and the balance, in that order.
- **Watching agents should feel like watching a team.** Spatial desks, color-coded voices and drawn wires turn a multi-agent run into something you can follow at a glance: the Boss lights up, hands to Inventory, a brass wire draws, Inventory's dot pulses, and the report appears.
- **Money needs a little ceremony.** A cheque with the amount in words, a typed signature and the balance-after shown up front makes a human slow down for exactly one second before paying, which is the right amount of friction. The count-down and the ledger line confirm the result without a page refresh.

## Screenshots

| File | Shows |
|---|---|
| `design_images/floor.png` | Ticket 103 after its run: lit desks, including the Accounting → Inventory wire, the wire log, and checking at $160.00 in brick below the cushion |
| `design_images/shift_report.png` | Ticket 103's shift report: the Boss's call, crew cards, facts with sources, and the draft letter to Yale AI Club |
| `design_images/after_payment.png` | Ticket 102 after signing: the paid-out ledger, RESOLVED stamps, and the "Signed by Deesha Malpure" line on the verdict |

The original version of this desk used a black-and-pink theme; it was redesigned to match the HW4 storefront. Screenshots in `output/resolved_board.html` were taken during the Problem 9 run, before the redesign.

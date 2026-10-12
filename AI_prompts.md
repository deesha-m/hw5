# AI Prompts

This file records the prompts used while working on Homework 5.

## Problem 1: Vibe Coder Prompts

### Initial prompt

Create AI_prompts.md at the start of the assignment and keep it updated as we work, one problem at a time. Create one section for each problem. Each section must include the problem number and title, at least one prompt I typed summarized, and one follow-up prompt if we needed it, with one sentence on what was lacking after the first.

### Follow-up prompt

No follow-up prompt was needed.

## Problem 2: Study the Campus Customs Database

### Initial prompt

Open `data/campus_customs.db` and look through every table and its fields. Copy the original to `data/campus_customs_new.db` as the working copy that later problems will update. Study the three open tickets to see how they link to other tables. Start `output/harness.md`, listing each table's fields with one short line on why that table matters for the agents.

**Agent action:** The agent opened the database read-only and read all 24 rows across the 9 tables. It copied the file and confirmed the copy was identical, then checked that every ticket link resolves. It traced each open ticket: the size-S tee is sold out and its reprint is tied to an overdue $840 invoice; the $2,400 rent is due in 2 days; and the hoodie group wants 20 in size M when only 8 are in stock. Paying both bills would leave $160 in checking.

### Follow-up prompt

No follow-up prompt was needed.

## Problem 3: Build the MCP Server

### Initial prompt

Write an MCP server in `mcp_server/` using FastMCP that talks to `data/campus_customs_new.db`. It doesn't need to be connected or run yet. Every agent in the homework will use its tools, and more will be added later. For now, write three clearly named tools needed for the tickets in the database, and never invent data, only use what's in the database. In `output/harness.md`, list each tool with the table it reads, the ticket it unlocks (101, 102 or 103), and one sentence on why it's the right tool for that ticket. Add a short `mcp_server/README.md` explaining what the server is for, which database it uses and its three tools.

**Agent action:** The agent set up `.venv` and found that the official `mcp` 2.x package had renamed FastMCP, so it used the standalone `fastmcp` package instead. It wrote three read-only tools, one per ticket, each returning a typed result and using the desk date as "today":
- `check_stock` for ticket 101,
- `get_lease` for ticket 102,
- `get_pricing` for ticket 103.

Unknown SKUs, sizes and lease IDs return errors listing the valid options. It tested all three tools and the error cases through an in-memory MCP client and confirmed the database was unchanged.

### Follow-up prompt

No follow-up prompt was needed.

## Problem 4: Add the MCP Server to Vibe Coder and Test Each Tool

### Initial prompt

Add the MCP server to the project so the vibe coder can call its tools, saving the connection JSON in `.mcp.json` at the project root. With the vibe coder connected, test each of the three tools and save the evidence in `output/mcp_smoke.json`, including the prompt, the tool name and the tool output for each, with outputs matching `data/campus_customs_new.db`.

**Agent action:** The agent wrote `.mcp.json` to launch the server with the project's `.venv` Python. `claude mcp list` showed the server waiting for approval, so the agent approved it in `.claude/settings.local.json` and confirmed it connected. After a session restart, it asked one question per ticket and called `check_stock`, `get_lease` and `get_pricing` live through MCP. It checked every returned value against the database with SQL (19 of 19 checks passed) and saved the prompts, tool names, outputs and checks to `output/mcp_smoke.json`.

### Follow-up prompt

No follow-up prompt was needed.

## Problem 5: Build the Agent Team and Grow the MCP Tools

### Initial prompt

Build the Campus Customs agent team in PydanticAI: Boss, Inventory, Accounting, Facilities and Customer Service. Give them prompts, models and agent loops so they can delegate work to each other with full connectivity. Put one prompt per agent in `backend/prompts/`, the data types in `backend/models.py`, and the agent files under `backend/`. Use `PORTKEY_API_KEY` and only `gpt-6-luna` for every agent. Write each prompt in my own words with the shop rules that agent needs, as detailed as possible. Add whatever MCP tools the agents need to work the open tickets. Shop facts must come from the MCP server, with no second tools layer that bypasses it. Have the agents append to `output/audit_trail.json` for every agent-loop step, never wiping it. In `output/harness.md`, list each agent and each MCP tool with its table, and add a short safety section with business guardrails and token limits. Update `mcp_server/README.md` to match the tools.

**Agent action:** The agent added 10 MCP tools (13 in total). These include two guarded write tools: `record_payment` checks the human approver, exact amount, no double payment and no overdraft; `update_ticket` only appends notes. It built the five agents over one shared MCP connection, each limited to its role's tools, with:
- a `delegate` tool that reaches every teammate, with loop, depth and count caps;
- code guardrails: no payment without a human approval for that item, only the Boss resolves tickets, and every dollar amount must come from a tool;
- team-wide token, request and step limits;
- an audit entry appended at every loop step.

It tested the guardrails and limits offline with a scripted model. `gpt-6-luna` rejected tool calls on the chat endpoint, so it switched to the Responses API. It then ran all three tickets live on scratch copies of the database. Reviewing ticket 103, it found the Boss had given 15% on only 8 hoodies, so it tightened the discount rules and re-ran 103 to confirm the fix. The working database was left unchanged.

### Follow-up prompt

No follow-up prompt was needed.

## Problem 6: Plan the Three Tickets

### Initial prompt

Before wiring the backend, write down what I expect the team to do on each open ticket. Build `output/desk_tickets.html`, a double-clickable page with one tab per ticket (101, 102, 103) plus empty Cash and Reflection tabs for later. On each ticket tab, fill only an Expected section, leaving room for an Actual section after the agents run. Each Expected section should say who the Boss calls first and why, every delegation I expect (not "Boss calls everyone"), and which MCP tools the run should use. Plans that send every specialist on every ticket score low.

**Agent action:** The agent built a self-contained black-and-pink page with five tabs. Each ticket tab has:
- a highlighted "Boss calls first" card with the reasoning;
- the expected delegations in order, with the task each agent gets and the facts it should find;
- a roster showing which agents are and aren't used, and why;
- an expected-tools table marking read, write and not-expected tools;
- an expected-outcome box;
- a dashed Actual placeholder.

The plan uses 8 delegations across the three tickets instead of 12. Facilities only works the rent ticket, and Customer Service skips it. The agent added a §6 summary table to the harness.

### Follow-up prompt

No follow-up prompt was needed.

## Problem 7: Backend API for the Dashboard

### Initial prompt

The React dashboard in the next problem needs a backend. In `backend/main.py`, use FastAPI to add routes that:
- return the three tickets and whether each is open or resolved;
- take a ticket id and run the agent team on it;
- return recent agent events (what each agent said and which tools it used) so the board can refresh;
- approve a payment or purchase after a human clicks Approve, since agents only prepare the payment and this route is what actually changes cash;
- return the current checking balance from `cash_accounts`;
- reset the database to the original values for a fresh run.

It should start from `backend/` with `uvicorn main:app --reload --port 8000`. List each route in one line in `output/harness.md`.

**Agent action:** The agent built 10 routes that read and change data only through the MCP server, adding a `list_tickets` tool. Agent runs start in the background and are polled through an events route built from the audit trail. Runs from the API get no payment approvals, so Accounting prepares a structured `ApprovalRequest` (`pay_kind`, `pay_ref_id`). The approve route pays only an item an agent prepared, at the exact amount on file, with a human name, and signs a note on the ticket.

During testing it found the board was showing Problem 5's scratch-database test runs as real history. So reset now logs a `db_reset` marker, and the board counts only working-database runs since then. The agent also made tool-only steps and delegate replies readable.

It tested the whole flow live (run ticket 101, poll events, approve $840, check cash, reject a wrong amount, an agent approver and a double approval) and reset the database afterward.

### Follow-up prompt

No follow-up prompt was needed.

## Problem 8: Agent Dashboard

### Initial prompt

Build the dashboard in `frontend/` with React + Vite + TypeScript, calling the Problem 7 routes. At minimum the board should:
- list the three tickets;
- let me pick one and start the agent team;
- show each agent and what it's saying or doing during the run;
- mark the ticket resolved when the run finishes;
- summarize what each agent did;
- let a human approve a payment or purchase;
- show the checking balance dropping after an approved payment.

Make it look good and creative, like a real desk people would want to sit at. Point it at `http://localhost:8000`, allow the Vite origin in the backend's CORS, and start it with `npm run dev`. Write `output/design.md` explaining the look (layout, how agents read differently, how resolved tickets and cash show up) and why.

**Agent action:** The agent built a three-column "back-office desk" in black and neon pink:
- **Ticket spike:** paper stubs with rubber-stamp states.
- **Floor:** five desks, each with its own color, glyph, lamp and speech bubble, joined by wires that light up during hand-offs. The Boss sits in the center.
- **Wire:** a live event log indented by delegation depth.
- **Shift report:** the Boss's call, a card per agent, facts with sources, and the customer reply as a "draft · not sent" letter.
- **Register:** an LED checking display that counts down after a payment and prints a receipt line.
- **Cheques:** agent-prepared payments with the amount in words and a typed signature.

The agent also changed the backend so a ticket resolves when its run finishes, or right after the human signs if a payment is waiting. It tested tickets 102 (sign and pay) and 103 (auto-resolve) live in Chromium with Playwright, fixed the layout issues the screenshots showed, saved screenshots to `output/design_images/`, wrote `output/design.md`, and reset the database.

### Follow-up prompt

Update the dashboard to match the aesthetic of the Homework 4 site: tech minimalist, Yale colors, modern.

**What was lacking after the first prompt:** The black-and-pink neon desk didn't match the Campus Customs brand I'd built in Homework 4, so the storefront and the back office felt like two different shops.

**Agent action:** The agent restyled the desk in the HW4 language, made more minimal:
- ivory paper, hairline cards and Yale Blue as the one accent, with a "CC" seal and serif wordmark;
- Cormorant Garamond, Inter, IBM Plex Mono and Caveat, plus Source Serif 4 for number-heavy text, because Cormorant only has old-style figures;
- agent colors re-tuned for a light page (Yale Blue, brass, green, brick, light blue).

The layout and features stayed the same. It rewrote `output/design.md`, retook the design screenshots, and opened the updated desk.

## Problem 9: Resolve the Tickets

### Initial prompt

Reset the working database so the run starts clean, and note the starting checking balance. Then run all three tickets on the board until each is resolved. In `output/desk_tickets.html`:
- fill the Actual section on each ticket tab (which agents worked, what they delegated, which tools they used), keeping the Expected section for comparison;
- itemize the money on the Cash tab: the starting balance, how cash changed when each ticket resolved and why, and the ending balance, which must match `cash_accounts`.

Also save `output/resolved_tickets.json` (id, final status, outcome, each agent's contribution, human approvals) and `output/resolved_board.html` (a board screenshot for each resolved ticket). Append the real runs to the audit trail and finish `output/harness.md` so it covers the tables, MCP tools, five agents, API routes, dashboard and safety rules.

**Agent action:** The agent drove the React board in Chromium with Playwright:
1. clicked **Fresh start**, with a starting balance of $3,400.00;
2. ran 101, 102 and 103 in turn;
3. signed the two cheques the agents prepared, as Deesha Malpure: $840.00 for invoice 501 and $2,400.00 for rent;
4. waited for each RESOLVED stamp.

It checked every run in the audit trail and the database before writing anything up. The cash reconciles: $3,400.00 − $840.00 − $2,400.00 − $0.00 = $160.00, matching `cash_accounts`.

It filled the Actual sections with plan-vs-actual tables:
- 101 matched the plan;
- 102 used only Facilities, which prepared the payment instead of Accounting;
- 103 sent three hand-offs in parallel and needed 5 delegations instead of 3, with one refused loop.

It added the Cash ledger, wrote `resolved_tickets.json` from the audit trail, and built `resolved_board.html` with 10 clean screenshots. It finished the harness with an overview, architecture, quick start, file map, the 14 MCP tools, API and dashboard guardrails in the safety section, and a §9 on results and lessons. The working database was left in its final state.

### Follow-up prompt

No follow-up prompt was needed.

## Problem 10: Reflection

### Initial prompt

Fill the Reflection tab of `output/desk_tickets.html` in my own voice, in detail. Cover:
- how well the agents performed on each ticket and why;
- how each ticket's Actual compared to the Expected plan;
- what would have been simpler as one agent with tools;
- three new problems Campus Customs could face that this team could solve with the tools built;
- three it couldn't, with the tools and agents needed to solve them.

Tie every answer to this app and the three tickets, using the ticket tabs and Cash tab as evidence.

**Agent action:** The agent pulled overhead numbers from the audit trail: 37 MCP calls where about 15 distinct facts were needed, 46 model requests, 147,854 tokens, and `get_ticket` re-read 12 times. It checked the "can solve" examples with live read-only MCP calls: 30 caps are in stock at $19.80 each / $594.00, rent is due 2026-10-02 against $160, and the Crest Mug is sold out.

It wrote the Reflection tab with:
- a scorecard (101 A, 102 B+, 103 B−) and per-ticket grades on correctness, safety, efficiency and customer-readiness;
- a plan-vs-actual table linked to each ticket tab;
- an honest "one agent would have been simpler" analysis with a call-count table;
- three solvable problems: a 30-cap bulk order, the October rent with $160 in checking, and a duplicate or fake invoice;
- three unsolvable ones with the tools and agents they'd need: recording sales and restocks (no inventory writes and no deposits, so cash only goes down), the October cash crunch (Treasury agent, forecast and transfer tools), and actually sending, receiving and shipping (Communications agent, inbox, verified contacts, courier);
- a closing "if I did it again" list.

### Follow-up prompt

No follow-up prompt was needed.

## Problem 11: Submit to GitHub

### Initial prompt

Push the code to a public GitHub repository so graders can clone it, and give me the repo URL for Canvas, also saved in `output/github_url.txt`. Don't push the real `.env`, but include both database files under `data/` so graders can run the app easily. Follow the expected layout. The README should explain how to copy the original database to the working copy for a clean run, start the MCP server, start the FastAPI backend, start the React board, and reset the database before a full three-ticket run.

**Agent action:** The agent asked about the repo name, whether to keep `agents.py` and `audit.py` separate, and whether to scrub local paths from the audit trail. Based on the answers, it:
- made the app record database paths relative to the project, and rewrote earlier absolute paths in the audit trail, so the board in a fresh clone still shows the Problem 9 history;
- made `.mcp.json` portable and confirmed it still connects;
- wrote the README and `github_url.txt`;
- scanned the staged files for keys and personal paths;
- created the public repo `deesha-m/hw5`, pushed, and verified a fresh clone (both databases present, no `.env`, backend serving the resolved tickets).

### Follow-up prompt

No follow-up prompt was needed.

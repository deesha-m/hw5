# Campus Customs: Back-Office Agent Team

MGT 409 AI Foundations for Managers, Homework 5.

A five-agent back office for Campus Customs, a small Yale apparel shop. The **Boss**, **Inventory**, **Accounting**, **Facilities** and **Customer Service** agents work the shop's tickets. All shop data comes through an **MCP server** over a SQLite database. A **FastAPI** backend and a **React** dashboard let a human watch the agents live and sign anything that moves money.

- **Agents:** PydanticAI, every agent on `gpt-6-luna` through Portkey (`PORTKEY_API_KEY`). Any agent can delegate to any other.
- **MCP server:** FastMCP, 14 tools, `mcp_server/server.py`.
- **Backend:** FastAPI, `backend/main.py`.
- **Dashboard:** React + Vite + TypeScript, `frontend/`.
- **Docs:** `output/harness.md` is the full reference for tables, tools, agents, routes, dashboard, safety and results. `output/design.md` covers the dashboard design.

## Layout

```
hw5/
├── AI_prompts.md            # prompt log, one section per problem
├── README.md
├── requirements.txt         # Python packages
├── .env.example             # copy to .env and add PORTKEY_API_KEY (never commit .env)
├── .gitignore
├── .mcp.json                # connects Claude Code (the vibe coder) to the MCP server
├── data/
│   ├── campus_customs.db       # ORIGINAL snapshot: never changed, used for resets
│   └── campus_customs_new.db   # WORKING copy the agents and dashboard change
├── mcp_server/
│   ├── server.py            # FastMCP server: all shop data access (14 tools)
│   └── README.md
├── backend/
│   ├── main.py              # FastAPI routes for the dashboard
│   ├── models.py            # all Pydantic data types
│   ├── agents.py            # the five PydanticAI agents, delegation, guardrails, CLI
│   ├── audit.py             # append-only writer for output/audit_trail.json
│   └── prompts/             # one system prompt per agent
│       ├── boss.md
│       ├── inventory.md
│       ├── accounting.md
│       ├── facilities.md
│       └── customer_service.md
├── frontend/                # React + Vite + TypeScript dashboard
└── output/
    ├── harness.md
    ├── mcp_smoke.json
    ├── desk_tickets.html        # plan vs. actual per ticket, Cash, Reflection
    ├── design.md                # + design_images/
    ├── resolved_tickets.json
    ├── resolved_board.html      # + resolved_board_images/
    ├── audit_trail.json
    └── github_url.txt
```

`backend/agents.py` and `backend/audit.py` sit next to `main.py` and `models.py`, so each of the five roles is clearly defined in one place: its prompt file, its tool list in `agents.py`, and its data types in `models.py`.

## 1. One-time setup

You need Python 3.11+ and Node.js 20+. Run these from the `hw5/` folder:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env              # then put your Portkey key in .env: PORTKEY_API_KEY=...
cd frontend && npm install && cd ..
```

The agents read `PORTKEY_API_KEY` from `hw5/.env`, or from a course `.env` two folders up. Without a key, everything except running the agents still works: tickets, cash, reset and the board.

## 2. Clean run: copy the original database to the working copy

`data/campus_customs_new.db` is committed in its **final state after the graded run** (all three tickets resolved, checking at $160.00). That way the board and `output/` files match what you see. To start fresh, copy the original over the working copy:

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

There are two ways to do the same thing once the backend is running:
- the **↺ Fresh start** button on the board (click it twice);
- `curl -X POST http://localhost:8000/api/reset`.

A clean database has 3 open tickets (101, 102, 103), $3,400.00 in checking and no payments.

## 3. Start the MCP server

The MCP server is how every agent, the backend and the vibe coder read and change shop data. It speaks MCP over stdio:

```bash
.venv/bin/python mcp_server/server.py
```

You usually don't have to start it by hand:
- **The backend starts it.** It launches its own MCP connections (one for the routes, one for the agent team) when it starts.
- **Claude Code starts it.** It launches the server from `.mcp.json` when you open this folder. Approve the `campus-customs` server when asked, then check with `claude mcp list`.

Set `CAMPUS_CUSTOMS_DB=/path/to/copy.db` to point the server at a different database file.

## 4. Start the FastAPI backend

```bash
cd backend
../.venv/bin/uvicorn main:app --reload --port 8000
```

- It runs at http://localhost:8000, with API docs at http://localhost:8000/docs.
- **Main routes:**
  - `GET /api/tickets`, `POST /api/tickets/{id}/run`, `GET /api/events`
  - `GET/POST /api/approvals`, `GET /api/cash`, `POST /api/reset`
- CORS allows the Vite dev page at `http://localhost:5173`.

## 5. Start the React board

In a second terminal:

```bash
cd frontend
npm run dev
```

Open http://localhost:5173. The board talks to `http://localhost:8000`; set `VITE_API_URL` in `frontend/.env` to change that.

## 6. A full three-ticket run

1. **Reset the database first:** either `cp data/campus_customs.db data/campus_customs_new.db` or **Fresh start** on the board. Checking should read **$3,400.00**.
2. **Ticket 101 (Bulldog tee):** select it and click **Hand it to the Boss →**. Watch the floor light up as the Boss → Inventory → Accounting → Customer Service hand-offs happen. When it finishes, a cheque for **$840.00 to Bulldog Print Co** (invoice 501) appears. Type your name and click **Approve & pay**. Checking drops to **$2,560.00** and the ticket is stamped RESOLVED.
3. **Ticket 102 (Rent due):** run it. Facilities verifies the emailed notice against lease 1, and a cheque for **$2,400.00 to Elm City Properties** appears, warning that checking will fall below the $500 cushion. Sign it, and checking drops to **$160.00**.
4. **Ticket 103 (Bulk hoodies):** run it. The team offers the standard 10% bulk discount ($52.20 each, $1,044.00 for 20 as a size mix). No money moves, and the ticket resolves when the run ends.

Ending balance: $3,400.00 − $840.00 − $2,400.00 = **$160.00**, which equals `cash_accounts` in the working database. Agents only *prepare* payments; your signature on the board is the only thing that moves cash.

Each run calls the model, which costs about 25k to 80k tokens per ticket. Exact routing can vary from run to run.

## Run the agent team from the command line (optional)

```bash
.venv/bin/python backend/agents.py --ticket 101
.venv/bin/python backend/agents.py --task "What's still open today?"
.venv/bin/python backend/agents.py --ticket 102 --db /tmp/test-copy.db
```

## Notes

- **Secrets:** the real `.env` is never committed (see `.gitignore`), and `.env.example` has placeholders only.
- **Audit trail:** `output/audit_trail.json` is append-only. Every agent-loop step is added as it happens. Resets are logged as `db_reset`, and putting the working database back to a saved state is logged as `db_restore`. The board shows runs since the latest of those markers. Database paths in the log are relative to this folder.
- **More detail:** `output/harness.md` has the tables, MCP tools, agents, routes, dashboard, safety rules, limits and the results of the graded run.

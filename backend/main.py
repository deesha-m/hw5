"""Campus Customs back-office API (FastAPI) for the React dashboard.

Start it from the backend/ folder:
    ../.venv/bin/uvicorn main:app --reload --port 8000

Shop data is read and changed only through the MCP server (mcp_server/server.py over
data/campus_customs_new.db), the same tools the agents use. Agents are run with no payment
approvals, so they can only prepare payments; POST /api/approvals is the one place a
human's click turns into a record_payment call that changes cash.
"""

import asyncio
import hashlib
import json
import os
import shutil
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from fastmcp.exceptions import ToolError

import audit
from agents import DEFAULT_DB, HW_ROOT, MCP_SERVER, Team, new_run_id, project_path, ticket_task
from models import (
    ROLE_TITLES,
    AgentEvent,
    AuditEntry,
    ApproveRequest,
    ApproveResult,
    CashView,
    EventsPage,
    PendingApproval,
    ResetResult,
    RunStatus,
    TicketCard,
)

WORKING_DB = Path(os.getenv("CAMPUS_CUSTOMS_DB", DEFAULT_DB)).resolve()
ORIGINAL_DB = HW_ROOT / "data" / "campus_customs.db"
LOW_CASH = 500.0

# In-memory run registry (the audit trail is the permanent record).
runs: dict[str, RunStatus] = {}
running_tickets: dict[int, str] = {}  # ticket id -> team_run_id while running
state: dict[str, Any] = {}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # One MCP connection for the routes and one shared agent team (with its own connection).
    transport = StdioTransport(
        command=sys.executable,
        args=[str(MCP_SERVER)],
        env={"CAMPUS_CUSTOMS_DB": str(WORKING_DB), "PATH": os.environ.get("PATH", ""), "FASTMCP_LOG_LEVEL": "WARNING"},
    )
    async with Client(transport) as mcp, Team(WORKING_DB) as team:
        state["mcp"], state["team"] = mcp, team
        yield
    state.clear()


app = FastAPI(title="Campus Customs Back Office API", version="1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def mcp_call(name: str, args: dict[str, Any] | None = None) -> Any:
    """Call an MCP tool and return its structured result. Tool refusals become HTTP 400s."""
    try:
        result = await state["mcp"].call_tool(name, args or {})
    except ToolError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    data = result.structured_content
    return data.get("result", data) if isinstance(data, dict) and set(data) == {"result"} else data


# --- Audit trail helpers ----------------------------------------------------------


def read_audit() -> list[dict[str, Any]]:
    if not audit.AUDIT_PATH.exists():
        return []
    try:
        return json.loads(audit.AUDIT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []  # mid-write; the next poll will read it


def board_entries(entries: list[dict[str, Any]]) -> list[tuple[int, dict[str, Any]]]:
    """(position, entry) for runs that count on the board: after the last reset, and only
    team runs against the working database (test runs on scratch copies are left out)."""
    start = max((i for i, e in enumerate(entries) if e["event"] == "db_reset"), default=-1) + 1
    run_db = {
        e["team_run_id"]: project_path(e["database"]) if e.get("database") else None
        for e in entries[start:]
        if e["event"] == "run_start" and not e.get("parent_agent")
    }
    working = project_path(WORKING_DB)
    return [
        (i, e) for i, e in enumerate(entries[start:], start)
        if e["event"] == "db_reset" or run_db.get(e["team_run_id"]) == working
    ]


def ticket_of_run(entries: list[dict[str, Any]]) -> dict[str, int]:
    """team_run_id -> ticket id, from the entry stamp or (older runs) the task text."""
    out: dict[str, int] = {}
    for e in entries:
        tid = e.get("ticket_id")
        if tid is None and e["event"] == "run_start" and not e.get("parent_agent"):
            task = e.get("task") or ""
            if task.startswith("Handle ticket "):
                digits = task[len("Handle ticket "):].split(":")[0]
                tid = int(digits) if digits.isdigit() else None
        if tid is not None:
            out.setdefault(e["team_run_id"], tid)
    return out


def latest_reports(entries: list[dict[str, Any]]) -> dict[int, tuple[str, dict[str, Any]]]:
    """ticket id -> (team_run_id, final top-level report) for the most recent finished run."""
    entries = [e for _, e in board_entries(entries)]
    tickets = ticket_of_run(entries)
    out: dict[int, tuple[str, dict[str, Any]]] = {}
    for e in entries:
        if e["event"] == "run_end" and not e.get("parent_agent") and e.get("output"):
            tid = tickets.get(e["team_run_id"])
            if tid is not None:
                out[tid] = (e["team_run_id"], e["output"])
    return out


# --- Routes -----------------------------------------------------------------------------


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "database": project_path(WORKING_DB), "time": now()}


@app.get("/api/tickets", response_model=list[TicketCard])
async def list_tickets() -> list[TicketCard]:
    """The tickets, each open or resolved, with the latest agent run's outcome."""
    rows = await mcp_call("list_tickets")
    reports = latest_reports(read_audit())
    cards = []
    for r in rows:
        tid = r["ticket_id"]
        run_id, report = reports.get(tid, (None, {}))
        cards.append(
            TicketCard(
                ticket_id=tid, type=r["type"], requester=r["requester"], subject=r["subject"],
                status=r["status"], state="open" if r["is_open"] else "resolved",
                created_at=r["created_at"], running=tid in running_tickets,
                last_run_id=run_id, last_report_status=report.get("status"), last_summary=report.get("summary"),
            )
        )
    return cards


@app.get("/api/tickets/{ticket_id}")
async def get_ticket(ticket_id: int) -> dict[str, Any]:
    """One ticket in full, plus the latest Boss report for it."""
    ticket = await mcp_call("get_ticket", {"ticket_id": ticket_id})
    run_id, report = latest_reports(read_audit()).get(ticket_id, (None, None))
    return {"ticket": ticket, "last_run_id": run_id, "last_report": report, "running": ticket_id in running_tickets}


async def close_ticket(ticket_id: int, note: str, author: str) -> str | None:
    """Mark a ticket resolved (unless it already is) with a signed note. Returns the note."""
    ticket = await mcp_call("get_ticket", {"ticket_id": ticket_id})
    if ticket["status"] == "resolved":
        return None
    upd = await mcp_call("update_ticket", {"ticket_id": ticket_id, "status": "resolved", "note": note, "author": author})
    return upd["note_added"]


async def payments_waiting(ticket_id: int) -> list[PendingApproval]:
    return [p for p in await pending_approvals() if p.ticket_id == ticket_id]


async def _run_ticket(team_run_id: str, ticket_id: int) -> None:
    status = runs[team_run_id]
    try:
        result = await state["team"].run(ticket_task(ticket_id), approvals=[], team_run_id=team_run_id, ticket_id=ticket_id)
        status.result = result
        status.state = "finished" if result.report else "failed"
        status.error = result.error
        # The run is over: the desk marks the ticket resolved, unless a payment still
        # needs a human signature (then it resolves when that payment is approved).
        if result.report and not await payments_waiting(ticket_id):
            await close_ticket(
                ticket_id,
                f"Agent run {team_run_id} finished ({result.report.status}). {result.report.summary}"[:900],
                "Desk (run finished)",
            )
    except Exception as exc:  # noqa: BLE001
        status.state, status.error = "failed", f"{type(exc).__name__}: {exc}"
    finally:
        status.finished_at = now()
        running_tickets.pop(ticket_id, None)


@app.post("/api/tickets/{ticket_id}/run", response_model=RunStatus, status_code=202)
async def run_ticket(ticket_id: int, wait: bool = False) -> RunStatus:
    """Start the agent team on a ticket (Boss first). Returns at once; poll /api/events or
    /api/runs/{id}. Pass ?wait=true to block until the run finishes."""
    await mcp_call("get_ticket", {"ticket_id": ticket_id})  # 400 if the ticket doesn't exist
    if ticket_id in running_tickets:
        raise HTTPException(409, f"Ticket {ticket_id} is already being worked (run {running_tickets[ticket_id]}).")
    team_run_id = new_run_id()
    runs[team_run_id] = RunStatus(team_run_id=team_run_id, ticket_id=ticket_id, state="running", started_at=now())
    running_tickets[ticket_id] = team_run_id
    task = asyncio.create_task(_run_ticket(team_run_id, ticket_id))
    if wait:
        await task
    return runs[team_run_id]


@app.get("/api/runs/{team_run_id}", response_model=RunStatus)
async def get_run(team_run_id: str) -> RunStatus:
    if team_run_id not in runs:
        raise HTTPException(404, "No run with that id since the server started (see /api/events for older runs).")
    return runs[team_run_id]


def _args(args: Any) -> str:
    if not isinstance(args, dict):
        return str(args)
    return ", ".join(f"{k}={v}" for k, v in args.items() if k not in ("note", "author"))


def describe_step(e: dict[str, Any]) -> str | None:
    """A readable line for steps where the model called tools without writing text."""
    lines = []
    for c in e.get("tool_calls", []):
        if c["tool"] == "final_result":
            lines.append("Wrote its final report.")
        elif c["tool"] == "delegate" and isinstance(c["args"], dict):
            lines.append(f"Asked {ROLE_TITLES.get(c['args'].get('to'), c['args'].get('to'))}: {c['args'].get('task', '')}")
        else:
            lines.append(f"Called {c['tool']}({_args(c['args'])})")
    for r in e.get("tool_results", []):
        if r["tool"] == "final_result":
            lines.append(f"Report sent back for a fix: {r['result'][:200]}")
            continue
        if r["tool"] == "delegate":
            try:
                d = json.loads(r["result"].split(" …[truncated]")[0])
                summary = d.get("summary") or (d.get("report") or {}).get("summary") or d.get("reason")
            except ValueError:
                summary = None
            lines.append(f"Teammate replied: {summary or r['result'][:200]}")
        else:
            lines.append(f"{r['tool']} → {r['outcome']}")
    return "\n".join(lines) or None


@app.get("/api/events", response_model=EventsPage)
async def events(
    after: int = Query(-1, description="Only events with id greater than this."),
    ticket_id: int | None = None,
    team_run_id: str | None = None,
    limit: int = Query(200, ge=1, le=1000),
    all_history: bool = Query(False, description="Include runs before the last reset and test runs on other databases."),
) -> EventsPage:
    """Recent agent events (what each agent said, which tools it used), oldest first.
    By default only runs on the working database since the last reset."""
    entries = read_audit()
    tickets = ticket_of_run(entries)
    out: list[AgentEvent] = []
    selected = list(enumerate(entries)) if all_history else board_entries(entries)
    for i, e in selected:
        if i <= after:
            continue
        tid = e.get("ticket_id", tickets.get(e["team_run_id"]))
        if ticket_id is not None and tid != ticket_id:
            continue
        if team_run_id is not None and e["team_run_id"] != team_run_id:
            continue
        output = e.get("output") or {}
        said = e.get("task") if e["event"] == "run_start" else output.get("summary") or e.get("text") or e.get("error")
        said = said or describe_step(e)
        out.append(
            AgentEvent(
                id=i, timestamp=e["timestamp"], team_run_id=e["team_run_id"], ticket_id=tid,
                agent=e["agent"], parent_agent=e.get("parent_agent"), chain=e.get("chain", []),
                step=e.get("step", 0), event=e["event"], said=said,
                tools_called=[c for c in e.get("tool_calls", []) if c["tool"] != "final_result"],
                tool_results=[r for r in e.get("tool_results", []) if r["tool"] != "final_result"],
                report_status=output.get("status"), stop_reason=e.get("stop_reason"), error=e.get("error"),
            )
        )
    return EventsPage(events=out[-limit:], last_id=len(entries) - 1)


@app.get("/api/approvals", response_model=list[PendingApproval])
async def pending_approvals() -> list[PendingApproval]:
    """Payments the agents prepared that are still unpaid, at the exact amount on file now."""
    entries = [e for _, e in board_entries(read_audit())]
    tickets = ticket_of_run(entries)
    latest_run = {tid: run_id for tid, (run_id, _) in latest_reports(entries).items()}
    found: dict[tuple[str, int], PendingApproval] = {}
    for e in entries:
        run_id = e["team_run_id"]
        tid = tickets.get(run_id)
        if e["event"] != "run_end" or not e.get("output") or latest_run.get(tid) != run_id:
            continue
        for a in e["output"].get("approvals_needed", []):
            if a.get("kind") != "payment" or not a.get("pay_kind") or a.get("pay_ref_id") is None:
                continue
            key = (a["pay_kind"], int(a["pay_ref_id"]))
            if key in found:
                continue
            # Re-check against the database: still owed? exact amount? who is paid?
            try:
                if key[0] == "invoice":
                    inv = await mcp_call("get_invoice", {"invoice_id": key[1]})
                    if inv["status"] != "open":
                        continue
                    amount, payee = inv["amount"], inv["vendor"]["name"]
                else:
                    lease = await mcp_call("get_lease", {"lease_id": key[1]})
                    if lease["days_until_due"] > 10:
                        continue  # already paid for this period
                    amount, payee = lease["monthly_rent"], lease["landlord"]
            except HTTPException:
                continue
            found[key] = PendingApproval(
                ticket_id=tid, team_run_id=run_id, pay_kind=key[0], pay_ref_id=key[1], amount=amount,
                payee=payee, reference=a.get("reference", ""), reason=a.get("reason", ""), requested_by=e["agent"],
            )
    return list(found.values())


@app.post("/api/approvals", response_model=ApproveResult)
async def approve_payment(body: ApproveRequest) -> ApproveResult:
    """A human clicked Approve: pay it. This is the only route that moves cash.
    It must match a payment the agents prepared (see GET /api/approvals), and the MCP server
    re-checks the exact amount, that it's still owed, and that cash covers it."""
    pending = {(p.pay_kind, p.pay_ref_id): p for p in await pending_approvals()}
    prepared = pending.get((body.pay_kind, body.pay_ref_id))
    if prepared is None:
        raise HTTPException(
            409, f"No agent-prepared payment is waiting for {body.pay_kind} {body.pay_ref_id}. Run the ticket first."
        )
    if round(body.amount, 2) != round(prepared.amount, 2):
        raise HTTPException(400, f"Amount {body.amount:.2f} doesn't match the amount on file ({prepared.amount:.2f}).")
    result = await mcp_call(
        "record_payment",
        {"kind": body.pay_kind, "ref_id": body.pay_ref_id, "amount": body.amount, "approved_by": body.approved_by.strip()},
    )
    note = None
    if body.ticket_id is not None:
        p = result["payment"]
        text = (
            f"Payment {p['payment_id']} approved by {p['approved_by']} on the dashboard: "
            f"{p['kind']} {p['ref_id']}, ${p['amount']:,.2f} from {p['account']} "
            f"(balance ${result['account_balance_before']:,.2f} -> ${result['account_balance_after']:,.2f}). {result['marked']}."
        )
        ticket = await mcp_call("get_ticket", {"ticket_id": body.ticket_id})
        upd = await mcp_call(
            "update_ticket",
            {"ticket_id": body.ticket_id, "status": ticket["status"], "note": text, "author": f"{p['approved_by']} (human)"},
        )
        note = upd["note_added"]
        if not await payments_waiting(body.ticket_id):
            await close_ticket(body.ticket_id, f"Resolved after {p['approved_by']} approved payment {p['payment_id']}.", "Desk")
    return ApproveResult(
        payment=result["payment"], balance_before=result["account_balance_before"],
        balance_after=result["account_balance_after"], marked=result["marked"], ticket_note=note,
    )


@app.get("/api/cash", response_model=CashView)
async def cash() -> CashView:
    """The current checking balance from cash_accounts, plus payments made so far."""
    bal = await mcp_call("get_cash_balance", {"account": "checking"})
    payments = await mcp_call("list_payments")
    return CashView(
        account=bal["account"], balance=bal["balance"], balance_date=bal["balance_date"], as_of=bal["as_of"],
        low_cash=bal["balance"] < LOW_CASH, payments=payments,
    )


@app.post("/api/reset", response_model=ResetResult)
async def reset() -> ResetResult:
    """Put the original database back as the working copy, for a fresh run.
    The audit trail is NOT wiped (it's append-only); use events_after to hide older runs."""
    if running_tickets:
        raise HTTPException(409, f"Can't reset while tickets are running: {sorted(running_tickets)}.")
    shutil.copyfile(ORIGINAL_DB, WORKING_DB)
    digest = hashlib.sha256(WORKING_DB.read_bytes()).hexdigest()
    reset_id = f"reset-{new_run_id()}"
    audit.append_entry(
        AuditEntry(
            timestamp=now(), team_run_id=reset_id, agent_run_id=reset_id, seq=1, agent="dashboard",
            parent_agent=None, chain=[], step=0, event="db_reset", database=project_path(WORKING_DB),
            text=f"Working database reset from {ORIGINAL_DB.name} (sha256 {digest[:12]}…). Board history starts here.",
        )
    )
    return ResetResult(
        reset_at=now(), database=project_path(WORKING_DB), copied_from=project_path(ORIGINAL_DB),
        sha256=digest, events_after=len(read_audit()) - 1,
    )

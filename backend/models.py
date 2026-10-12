"""Data types for the Campus Customs agent team (PydanticAI).

Shop facts (stock, prices, invoices, cash, leases, tickets) are NOT modeled here: they
come from the MCP server (mcp_server/server.py), which owns its own return types. This
file holds what the agents produce, what they pass to each other, and the audit trail.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field

# --- The team ------------------------------------------------------------------

Role = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]

ROLE_TITLES: dict[str, str] = {
    "boss": "Boss",
    "inventory": "Inventory",
    "accounting": "Accounting",
    "facilities": "Facilities",
    "customer_service": "Customer Service",
}


# --- What every agent returns ---------------------------------------------------


class Fact(BaseModel):
    """One checked fact, tied to the tool that returned it, so a reviewer can trace it."""

    statement: str = Field(description="The fact in plain words, e.g. 'CC-TEE-WHITE size S has 0 on hand'.")
    source: str = Field(description="The MCP tool (or delegated agent) that returned it, e.g. 'check_stock'.")


class ApprovalRequest(BaseModel):
    """Something only a human may decide: a payment, a discount beyond policy, an exception."""

    kind: Literal["payment", "discount", "policy_exception", "other"]
    reference: str = Field(description="What it's for, e.g. 'invoice 501', 'lease 1 rent', 'ticket 103'.")
    amount: float | None = Field(default=None, description="Dollar amount, copied from a tool result.")
    reason: str = Field(description="Why it's needed and what the agent recommends.")
    pay_kind: Literal["invoice", "rent"] | None = Field(
        default=None, description="For payments: what a human would pay from the dashboard (invoice or rent)."
    )
    pay_ref_id: int | None = Field(default=None, description="For payments: the invoice id or the lease id.")


class AgentReport(BaseModel):
    """The structured answer every agent (including the Boss) ends its run with."""

    role: Role
    ticket_ids: list[int] = Field(default_factory=list, description="Tickets this report is about.")
    status: Literal["done", "waiting_on_approval", "blocked", "escalated", "refused"] = Field(
        description="done: finished within the rules. waiting_on_approval: a human must approve something. "
        "blocked: can't proceed (missing data, vendor, stock). escalated: handed to a human for a judgment call. "
        "refused: the request breaks a shop rule."
    )
    summary: str = Field(description="2 to 5 sentences: what was found, decided and done.")
    facts: list[Fact] = Field(default_factory=list, description="The key facts behind the summary, each with its source.")
    actions_taken: list[str] = Field(
        default_factory=list, description="Changes actually made through tools (payments, ticket updates). Empty if none."
    )
    approvals_needed: list[ApprovalRequest] = Field(default_factory=list)
    customer_message: str | None = Field(
        default=None, description="A draft message for the requester. Drafted only, never sent by an agent."
    )
    next_steps: list[str] = Field(default_factory=list, description="What should happen next, and who does it.")


class DelegationResult(BaseModel):
    """What the `delegate` tool hands back to the agent that asked for help."""

    to: Role
    task: str
    outcome: Literal["completed", "refused", "failed"] = Field(
        description="completed: the teammate returned a report. refused: the delegation broke a team rule "
        "(loop, depth or budget). failed: the teammate's run errored."
    )
    report: AgentReport | None = None
    reason: str | None = Field(default=None, description="Why it was refused or failed.")


# --- Human approvals and run context ------------------------------------------------


class PaymentApproval(BaseModel):
    """A payment a named human approved for this run. Without one, no money moves."""

    kind: Literal["invoice", "rent"]
    ref_id: int = Field(description="Invoice id or lease id.")
    approved_by: str = Field(description="The human who approved it.")


@dataclass
class TeamBudget:
    """Counters shared by every agent in one team run (passed by reference)."""

    delegations: int = 0


@dataclass
class TeamDeps:
    """Per-agent-run context. The child of a delegation gets a copy with role/chain/depth updated."""

    team_run_id: str
    role: str
    chain: tuple[str, ...]  # who delegated to whom to get here, e.g. ("boss", "accounting")
    approvals: list[PaymentApproval] = field(default_factory=list)
    budget: TeamBudget = field(default_factory=TeamBudget)
    audit: Any = None  # audit.AuditLogger, typed loosely to keep models.py import-free

    @property
    def depth(self) -> int:
        return len(self.chain) - 1

    @property
    def parent(self) -> str | None:
        return self.chain[-2] if len(self.chain) > 1 else None


class TeamResult(BaseModel):
    """What one team run returns to the caller (CLI or a later API)."""

    team_run_id: str
    ticket_id: int | None = None
    task: str
    report: AgentReport | None
    stop_reason: str = Field(description="final_output, usage_limit, step_limit or error.")
    error: str | None = None
    requests: int
    tool_calls: int
    input_tokens: int
    output_tokens: int
    delegations: int


# --- Audit trail (output/audit_trail.json) -----------------------------------------------


class AuditToolCall(BaseModel):
    tool_call_id: str
    tool: str
    args: dict[str, Any] | str


class AuditToolResult(BaseModel):
    tool_call_id: str
    tool: str
    outcome: Literal["ok", "error", "blocked"]
    result: str = Field(description="The tool's answer, shortened to keep the file readable.")


class AuditUsage(BaseModel):
    requests: int = 0
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


class AuditEntry(BaseModel):
    """One step of one agent's loop. Appended as it happens, never rewritten."""

    timestamp: str = Field(description="Wall-clock time (UTC) the step was logged.")
    team_run_id: str = Field(description="Groups every agent and step from one top-level request.")
    ticket_id: int | None = Field(default=None, description="The ticket the team run is working, if any.")
    agent_run_id: str = Field(description="One agent's run within the team run.")
    seq: int = Field(description="Order of this entry within the team run.")
    agent: str
    parent_agent: str | None = Field(description="Who delegated to this agent (None for the top-level agent).")
    chain: list[str] = Field(description="Full delegation path, e.g. ['boss', 'accounting'].")
    step: int = Field(description="Loop step within this agent's run (0 = start).")
    event: Literal["run_start", "model_response", "tool_results", "run_end", "db_reset"] = Field(
        description="db_reset is written by the dashboard's reset route, so resets are on the record too."
    )
    task: str | None = Field(default=None, description="run_start: the task the agent was given.")
    database: str | None = Field(default=None, description="run_start of the top-level agent: which database file the MCP server used.")
    model: str | None = None
    text: str | None = Field(default=None, description="model_response: any text or reasoning summary the model wrote.")
    tool_calls: list[AuditToolCall] = Field(default_factory=list)
    tool_results: list[AuditToolResult] = Field(default_factory=list)
    step_usage: AuditUsage | None = Field(default=None, description="Tokens for this one model response.")
    team_usage: AuditUsage | None = Field(default=None, description="Running total for the whole team run.")
    stop_reason: str | None = Field(default=None, description="run_end: final_output, usage_limit, step_limit or error.")
    output: dict[str, Any] | None = Field(default=None, description="run_end: the agent's AgentReport.")
    error: str | None = None


# --- Dashboard API (backend/main.py) ------------------------------------------------


class TicketCard(BaseModel):
    """One ticket on the board."""

    ticket_id: int
    type: str
    requester: str
    subject: str
    status: str = Field(description="Database status: open, in_progress, waiting or resolved.")
    state: Literal["open", "resolved"] = Field(description="Simple board state: resolved, or still open.")
    created_at: str
    running: bool = Field(description="True while the agent team is working this ticket.")
    last_run_id: str | None = Field(default=None, description="Most recent team run for this ticket.")
    last_report_status: str | None = Field(default=None, description="The Boss's report status from that run.")
    last_summary: str | None = None


class RunStatus(BaseModel):
    """A team run started from the dashboard."""

    team_run_id: str
    ticket_id: int | None
    state: Literal["running", "finished", "failed"]
    started_at: str
    finished_at: str | None = None
    result: TeamResult | None = Field(default=None, description="Filled when the run finishes.")
    error: str | None = None


class AgentEvent(BaseModel):
    """One audit-trail step, shaped for the board: who acted, what they said, which tools."""

    id: int = Field(description="Position in output/audit_trail.json. Pass it back as ?after= to get only newer events.")
    timestamp: str
    team_run_id: str
    ticket_id: int | None
    agent: str
    parent_agent: str | None
    chain: list[str]
    step: int
    event: str = Field(description="run_start, model_response, tool_results or run_end.")
    said: str | None = Field(default=None, description="The task (run_start), the model's text, or the final report summary (run_end).")
    tools_called: list[AuditToolCall] = Field(default_factory=list)
    tool_results: list[AuditToolResult] = Field(default_factory=list)
    report_status: str | None = None
    stop_reason: str | None = None
    error: str | None = None


class EventsPage(BaseModel):
    events: list[AgentEvent]
    last_id: int = Field(description="The newest event id in the file. Use it as ?after= on the next poll.")


class PendingApproval(BaseModel):
    """A payment the agents prepared that is still waiting for a human."""

    ticket_id: int | None
    team_run_id: str
    pay_kind: Literal["invoice", "rent"]
    pay_ref_id: int
    amount: float = Field(description="The exact amount on file right now (from the MCP server), not the agent's number.")
    payee: str
    reference: str
    reason: str
    requested_by: str = Field(description="Which agent prepared it.")


class ApproveRequest(BaseModel):
    """Sent when a human clicks Approve on the board."""

    pay_kind: Literal["invoice", "rent"]
    pay_ref_id: int
    amount: float
    approved_by: str = Field(min_length=3, max_length=80, description="The human's full name.")
    ticket_id: int | None = None


class ApproveResult(BaseModel):
    payment: dict[str, Any] = Field(description="The payments row the MCP server wrote.")
    balance_before: float
    balance_after: float
    marked: str
    ticket_note: str | None = None


class CashView(BaseModel):
    account: str
    balance: float
    balance_date: str
    as_of: str
    low_cash: bool = Field(description="True when the balance is under the $500 cushion.")
    payments: list[dict[str, Any]] = Field(default_factory=list, description="Payments made so far, newest last.")


class ResetResult(BaseModel):
    reset_at: str
    database: str
    copied_from: str
    sha256: str = Field(description="Checksum of the working copy after reset (matches the original).")
    events_after: int = Field(description="Audit trail position at reset. Use as ?after= to hide older runs.")

"""Campus Customs agent team (PydanticAI): Boss, Inventory, Accounting, Facilities, Customer Service.

- Every agent's system prompt is its file in prompts/ (boss.md, inventory.md, ...).
- Every agent runs on gpt-6-luna through Portkey (PORTKEY_API_KEY from the course .env).
- Shop facts come ONLY from the MCP server (mcp_server/server.py over
  data/campus_customs_new.db). The team opens one stdio connection to it and each agent
  sees the subset of its tools that its role needs.
- Full connectivity: every agent has a `delegate` tool that can hand a task to any other
  agent, which runs its own loop and returns an AgentReport. Loops, depth and the
  total number of delegations are capped.
- Every agent-loop step is appended to output/audit_trail.json as it happens.

Run from the homework 5 folder:
    .venv/bin/python backend/agents.py --ticket 101
    .venv/bin/python backend/agents.py --ticket 102 --approver "Jane Doe" --approve rent:1
    .venv/bin/python backend/agents.py --task "What's open today?" --db /path/to/copy.db
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import os
import re
import sys
import uuid
from contextlib import AsyncExitStack
from dataclasses import replace
from pathlib import Path
from typing import Any

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from dotenv import load_dotenv
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from openai import AsyncOpenAI
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.messages import (
    ModelResponse,
    RetryPromptPart,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import RunUsage, UsageLimits

import audit
from models import (
    ROLE_TITLES,
    AgentReport,
    DelegationResult,
    PaymentApproval,
    Role,
    TeamBudget,
    TeamDeps,
    TeamResult,
)

BACKEND = Path(__file__).resolve().parent
HW_ROOT = BACKEND.parent
PROMPTS = BACKEND / "prompts"
MCP_SERVER = HW_ROOT / "mcp_server" / "server.py"
DEFAULT_DB = HW_ROOT / "data" / "campus_customs_new.db"

load_dotenv(HW_ROOT.parents[1] / ".env")  # the course .env in "AI Foundations/"
load_dotenv(HW_ROOT / ".env")  # optional local override

MODEL_NAME = "gpt-6-luna"  # the only model any agent uses

# --- Limits (keep one request from looping or running up the bill) -----------------------

# One budget shared by every agent in a team run (child runs add to the parent's usage).
TEAM_LIMITS = UsageLimits(request_limit=40, tool_calls_limit=60, total_tokens_limit=300_000)
MAX_STEPS_PER_AGENT = 10  # model responses in one agent's loop
MAX_DEPTH = 3  # boss -> a -> b -> c at most
MAX_DELEGATIONS = 8  # delegate calls per team run
# Responses API: Portkey routes gpt-6-luna to Azure, which rejects tool calls with
# reasoning on /chat/completions but allows them on /responses.
MODEL_SETTINGS = OpenAIResponsesModelSettings(max_tokens=6_000, openai_reasoning_effort="low", timeout=90)

# --- Which MCP tools each role may see (least privilege) ----------------------------------

TICKET_READ = {"get_ticket", "list_open_tickets", "update_ticket"}
ROLE_TOOLS: dict[str, set[str]] = {
    "boss": TICKET_READ | {"get_cash_balance", "list_invoices", "list_payments"},
    "inventory": TICKET_READ | {"check_stock", "get_pricing", "list_vendors", "get_invoice"},
    "accounting": TICKET_READ
    | {
        "get_invoice", "list_invoices", "list_vendors", "get_cash_balance", "list_payments",
        "get_lease", "get_pricing", "quote_discount", "record_payment",
    },
    "facilities": TICKET_READ | {"get_lease", "get_cash_balance", "list_payments"},
    "customer_service": TICKET_READ | {"check_stock", "get_pricing", "quote_discount"},
}
ROLES: tuple[str, ...] = tuple(ROLE_TOOLS)


def project_path(path: Path | str) -> str:
    """A path as recorded in the audit trail: relative to the homework folder when inside it,
    so the log is portable (and has no personal folder names)."""
    p = Path(path)
    p = (p if p.is_absolute() else HW_ROOT / p).resolve()
    try:
        return p.relative_to(HW_ROOT).as_posix()
    except ValueError:
        return str(p)


class StepLimitExceeded(RuntimeError):
    pass


# --- Model -----------------------------------------------------------------------------------

_model: OpenAIResponsesModel | None = None


def get_model() -> OpenAIResponsesModel:
    """gpt-6-luna through the Portkey gateway. Built once, on first use."""
    global _model
    if _model is None:
        key = os.getenv("PORTKEY_API_KEY")
        if not key:
            raise RuntimeError("PORTKEY_API_KEY was not found (expected in the course .env).")
        client = AsyncOpenAI(
            base_url="https://api.portkey.ai/v1",
            api_key=key,
            default_headers={"x-portkey-api-key": key, "x-portkey-provider": "openai"},
            timeout=90,
            max_retries=2,
        )
        _model = OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))
    return _model


# --- Guardrails on MCP calls (enforced in code, not just in the prompts) ------------------


def blocked(reason: str) -> dict[str, Any]:
    return {"blocked": True, "reason": reason}


async def guard_tool_call(ctx: RunContext[TeamDeps], call_tool, name: str, args: dict[str, Any]):
    """Runs before every MCP tool call. Refuses calls a role isn't allowed to make."""
    deps = ctx.deps
    if name not in ROLE_TOOLS[deps.role]:
        return blocked(f"{ROLE_TITLES[deps.role]} is not allowed to use {name}.")

    if name == "update_ticket":
        # Notes are always signed by the real agent, and only the Boss closes tickets.
        args = {**args, "author": f"{ROLE_TITLES[deps.role]} agent"}
        if str(args.get("status", "")).strip().lower() == "resolved" and deps.role != "boss":
            return blocked("Only the Boss can set a ticket to resolved. Use in_progress or waiting.")

    if name == "record_payment":
        kind = str(args.get("kind", "")).strip().lower()
        ref_id = args.get("ref_id")
        approval = next((a for a in deps.approvals if a.kind == kind and a.ref_id == ref_id), None)
        if approval is None:
            return blocked(
                f"No human approval for {kind} {ref_id} in this run. Do not pay. "
                "Report waiting_on_approval with an ApprovalRequest instead."
            )
        # The approver is whoever the human said, never what the model typed.
        args = {**args, "approved_by": approval.approved_by}

    return await call_tool(name, args)


# --- Grounding check on every report ----------------------------------------------------

_NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
_DOLLARS = re.compile(r"\$\s?(\d[\d,]*(?:\.\d+)?)")


def numbers_in(text: str) -> set[float]:
    out = set()
    for raw in _NUMBER.findall(text):
        try:
            out.add(round(float(raw.replace(",", "")), 2))
        except ValueError:
            pass
    return out


def grounded_numbers(ctx: RunContext[TeamDeps]) -> set[float]:
    """Every number that reached this agent from a tool result or its task."""
    seen: set[float] = set()
    for msg in ctx.messages:
        for part in getattr(msg, "parts", []):
            if isinstance(part, ToolReturnPart):
                seen |= numbers_in(part.model_response_str())
            elif isinstance(part, UserPromptPart) and isinstance(part.content, str):
                seen |= numbers_in(part.content)
    return seen


def is_grounded(value: float, seen: set[float]) -> bool:
    if any(abs(value - s) < 0.011 for s in seen):
        return True
    # Allow simple arithmetic on returned numbers (a total, a remaining balance).
    small = sorted(seen)[:200]
    for a, b in itertools.product(small, repeat=2):
        if abs(value - (a + b)) < 0.011 or abs(value - (a - b)) < 0.011 or abs(value - a * b) < 0.011:
            return True
    return False


async def check_report(ctx: RunContext[TeamDeps], report: AgentReport) -> AgentReport:
    """Reject a report whose dollar amounts no tool returned, and keep the role honest."""
    report.role = ctx.deps.role  # an agent can't report as someone else
    seen = grounded_numbers(ctx)
    texts = [report.summary, report.customer_message or "", *report.next_steps]
    texts += [f.statement for f in report.facts] + [a.reason for a in report.approvals_needed]
    amounts = {round(float(x.replace(",", "")), 2) for t in texts for x in _DOLLARS.findall(t)}
    amounts |= {round(a.amount, 2) for a in report.approvals_needed if a.amount is not None}
    unsupported = sorted(a for a in amounts if not is_grounded(a, seen))
    if unsupported:
        raise ModelRetry(
            f"These dollar amounts weren't returned by any tool in this run: {unsupported}. "
            "Call the tool that gives the exact number (e.g. quote_discount, get_invoice, get_cash_balance) "
            "or remove the amount."
        )
    return report


# --- Run context shown to each agent ------------------------------------------------


def run_context(ctx: RunContext[TeamDeps]) -> str:
    d = ctx.deps
    chain = " → ".join(ROLE_TITLES[r] for r in d.chain)
    others = [r for r in ROLES if r not in d.chain]
    if d.approvals:
        approvals = "\n".join(
            f"- {a.kind} {a.ref_id}: approved by {a.approved_by}" for a in d.approvals
        )
    else:
        approvals = "- None. No payment may be recorded in this run."
    return (
        "## This run\n"
        f"- You are: {ROLE_TITLES[d.role]} (`{d.role}`).\n"
        f"- Delegation chain so far: {chain}. Depth {d.depth} of max {MAX_DEPTH}.\n"
        f"- You may delegate to: {', '.join(f'`{r}`' for r in others) or 'nobody (everyone is in the chain)'}.\n"
        f"- Delegations used: {d.budget.delegations} of {MAX_DELEGATIONS} for the whole team.\n"
        f"- Every agent: model {MODEL_NAME}, at most {MAX_STEPS_PER_AGENT} steps each.\n\n"
        "## Human approvals for this run\n"
        f"{approvals}"
    )


# --- The team -----------------------------------------------------------------------------


class Team:
    """Five agents sharing one MCP connection. Use as `async with Team() as team:`."""

    def __init__(self, db_path: Path = DEFAULT_DB, model: Any = None):
        self.model = model  # tests pass a scripted model; normally gpt-6-luna via get_model()
        self.db_path = Path(db_path).resolve()
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")
        transport = StdioTransport(
            command=sys.executable,
            args=[str(MCP_SERVER)],
            env={
                "CAMPUS_CUSTOMS_DB": str(self.db_path),
                "PATH": os.environ.get("PATH", ""),
                "FASTMCP_LOG_LEVEL": "WARNING",
            },
        )
        self.mcp = MCPToolset(Client(transport), process_tool_call=guard_tool_call, tool_error_behavior="retry")
        self.agents: dict[str, Agent[TeamDeps, AgentReport]] = {r: self._build(r) for r in ROLES}
        self._stack = AsyncExitStack()

    async def __aenter__(self) -> "Team":
        await self._stack.enter_async_context(self.mcp)
        return self

    async def __aexit__(self, *exc) -> None:
        await self._stack.aclose()

    def _build(self, role: str) -> Agent[TeamDeps, AgentReport]:
        allowed = ROLE_TOOLS[role]
        agent = Agent(
            None,
            name=role,
            instructions=[(PROMPTS / f"{role}.md").read_text(encoding="utf-8"), run_context],
            output_type=AgentReport,
            deps_type=TeamDeps,
            toolsets=[self.mcp.filtered(lambda ctx, td: td.name in allowed)],
            model_settings=MODEL_SETTINGS,
            retries=2,
        )
        agent.output_validator(check_report)

        @agent.tool
        async def delegate(ctx: RunContext[TeamDeps], to: Role, task: str) -> DelegationResult:
            """Hand a task to a teammate and get their AgentReport back.

            to: boss, inventory, accounting, facilities or customer_service (not yourself,
            and not anyone already in the delegation chain).
            task: a specific request with the ticket id and the facts you already have.
            """
            return await self.delegate(ctx, to, task)

        return agent

    async def delegate(self, ctx: RunContext[TeamDeps], to: str, task: str) -> DelegationResult:
        d = ctx.deps
        if to not in ROLES:
            return DelegationResult(to="boss", task=task, outcome="refused", reason=f"Unknown teammate '{to}'.")
        if to in d.chain:
            return DelegationResult(
                to=to, task=task, outcome="refused",
                reason=f"{ROLE_TITLES[to]} is already in the chain ({' → '.join(d.chain)}); that would loop.",
            )
        if d.depth + 1 > MAX_DEPTH:
            return DelegationResult(to=to, task=task, outcome="refused", reason=f"Max delegation depth {MAX_DEPTH} reached.")
        if d.budget.delegations >= MAX_DELEGATIONS:
            return DelegationResult(
                to=to, task=task, outcome="refused", reason=f"Team used all {MAX_DELEGATIONS} delegations for this run."
            )
        d.budget.delegations += 1
        child = replace(d, role=to, chain=(*d.chain, to))
        brief = f"Delegated by {ROLE_TITLES[d.role]}.\n\nTask: {task}"
        try:
            report = await self.run_agent(child, brief, usage=ctx.usage)
        except UsageLimitExceeded:
            raise  # the team budget is spent: stop the whole run
        except Exception as exc:  # noqa: BLE001 - the parent should see the failure and carry on
            return DelegationResult(to=to, task=task, outcome="failed", reason=f"{type(exc).__name__}: {exc}"[:400])
        return DelegationResult(to=to, task=task, outcome="completed", report=report)

    async def run_agent(self, deps: TeamDeps, task: str, usage: RunUsage | None = None) -> AgentReport:
        """One agent's loop, stepped node by node so every step is audited as it happens."""
        log = deps.audit.log
        agent_run_id = uuid.uuid4().hex[:12]
        who = dict(agent_run_id=agent_run_id, agent=deps.role, parent_agent=deps.parent, chain=list(deps.chain))
        log(**who, step=0, event="run_start", task=task,
            model=MODEL_NAME if self.model is None else str(self.model.model_name),
            database=project_path(self.db_path) if deps.depth == 0 else None)
        step = 0
        names: dict[str, str] = {}
        run = None
        try:
            async with self.agents[deps.role].iter(
                task, deps=deps, model=self.model or get_model(), usage=usage, usage_limits=TEAM_LIMITS
            ) as run:
                async for node in run:
                    if Agent.is_call_tools_node(node):
                        step += 1
                        if step > MAX_STEPS_PER_AGENT:
                            raise StepLimitExceeded(f"{deps.role} passed {MAX_STEPS_PER_AGENT} steps")
                        log(**who, step=step, event="model_response", **self._response_fields(node.model_response, names))
                    elif Agent.is_model_request_node(node) and step > 0:
                        results = self._results(node.request.parts, names)
                        if results:
                            log(**who, step=step, event="tool_results", tool_results=results)
            report = run.result.output
            log(**who, step=step, event="run_end", stop_reason="final_output",
                output=report.model_dump(), team_usage=audit.usage(run.usage))
            return report
        except UsageLimitExceeded as exc:
            log(**who, step=step, event="run_end", stop_reason="usage_limit", error=str(exc),
                team_usage=audit.usage(run.usage if run else usage))
            raise
        except StepLimitExceeded as exc:
            log(**who, step=step, event="run_end", stop_reason="step_limit", error=str(exc),
                team_usage=audit.usage(run.usage if run else usage))
            raise
        except Exception as exc:
            log(**who, step=step, event="run_end", stop_reason="error", error=f"{type(exc).__name__}: {exc}"[:600],
                team_usage=audit.usage(run.usage if run else usage))
            raise

    @staticmethod
    def _response_fields(resp: ModelResponse, names: dict[str, str]) -> dict[str, Any]:
        text = "\n".join(
            p.content for p in resp.parts if isinstance(p, (TextPart, ThinkingPart)) and p.content
        )
        calls = []
        for p in resp.parts:
            if isinstance(p, ToolCallPart):
                names[p.tool_call_id] = p.tool_name
                calls.append(audit.tool_call(p.tool_call_id, p.tool_name, p.args))
        return dict(text=text or None, tool_calls=calls, step_usage=audit.usage(resp.usage), model=resp.model_name)

    @staticmethod
    def _results(parts, names: dict[str, str]) -> list:
        out = []
        for p in parts:
            if isinstance(p, ToolReturnPart):
                content = p.content.model_dump() if hasattr(p.content, "model_dump") else p.content
                if p.tool_name == "delegate" and isinstance(content, dict):
                    # Keep the teammate's answer readable in the log; its own run_end has the full report.
                    report = content.get("report") or {}
                    content = {
                        "to": content.get("to"), "outcome": content.get("outcome"),
                        "status": report.get("status"), "summary": report.get("summary"),
                        "reason": content.get("reason"),
                    }
                out.append(audit.tool_result(p.tool_call_id, p.tool_name, content, is_error=False))
            elif isinstance(p, RetryPromptPart) and p.tool_name:
                tool = names.get(p.tool_call_id, p.tool_name)
                out.append(audit.tool_result(p.tool_call_id, tool, p.model_response(), is_error=True))
        return out

    async def run(
        self,
        task: str,
        approvals: list[PaymentApproval] | None = None,
        role: str = "boss",
        team_run_id: str | None = None,
        ticket_id: int | None = None,
    ) -> TeamResult:
        """A top-level request: starts with the Boss (by default) and returns its report."""
        team_run_id = team_run_id or new_run_id()
        deps = TeamDeps(
            team_run_id=team_run_id, role=role, chain=(role,), approvals=approvals or [],
            budget=TeamBudget(), audit=audit.AuditLogger(team_run_id, ticket_id),
        )
        usage = RunUsage()
        report, stop, error = None, "final_output", None
        try:
            report = await self.run_agent(deps, task, usage=usage)
        except UsageLimitExceeded as exc:
            stop, error = "usage_limit", str(exc)
        except StepLimitExceeded as exc:
            stop, error = "step_limit", str(exc)
        except Exception as exc:  # noqa: BLE001
            stop, error = "error", f"{type(exc).__name__}: {exc}"
        return TeamResult(
            team_run_id=team_run_id, ticket_id=ticket_id, task=task, report=report, stop_reason=stop, error=error,
            requests=usage.requests, tool_calls=usage.tool_calls,
            input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
            delegations=deps.budget.delegations,
        )


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


def ticket_task(ticket_id: int) -> str:
    return f"Handle ticket {ticket_id}: read it, work it with the right teammates, and report the decision."


# --- CLI ---------------------------------------------------------------------------------


def parse_approvals(items: list[str], approver: str | None) -> list[PaymentApproval]:
    if items and not approver:
        raise SystemExit("--approve needs --approver \"Full Name\" (the human approving the payment).")
    out = []
    for item in items:
        kind, _, ref = item.partition(":")
        if kind not in ("invoice", "rent") or not ref.isdigit():
            raise SystemExit(f"--approve expects invoice:<id> or rent:<lease id>, got '{item}'.")
        out.append(PaymentApproval(kind=kind, ref_id=int(ref), approved_by=approver))
    return out


async def main() -> None:
    p = argparse.ArgumentParser(description="Run the Campus Customs agent team.")
    what = p.add_mutually_exclusive_group(required=True)
    what.add_argument("--ticket", type=int, help="Handle one open ticket, starting with the Boss.")
    what.add_argument("--task", help="Any back-office request, in plain words.")
    p.add_argument("--agent", choices=ROLES, default="boss", help="Which agent takes the request first.")
    p.add_argument("--approve", action="append", default=[], metavar="KIND:ID",
                   help="A human-approved payment, e.g. invoice:501 or rent:1. Repeatable.")
    p.add_argument("--approver", help="Name of the human approving the --approve payments.")
    p.add_argument("--db", type=Path, default=DEFAULT_DB, help="Database file (default: data/campus_customs_new.db).")
    a = p.parse_args()

    task = a.task or ticket_task(a.ticket)
    async with Team(a.db) as team:
        result = await team.run(task, parse_approvals(a.approve, a.approver), role=a.agent, ticket_id=a.ticket)
    print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    asyncio.run(main())

"""Append-only audit trail for the agent team: output/audit_trail.json.

The file is one JSON array. Each new entry is written over the closing "]" and a new "]"
is added, so earlier entries are never rewritten and the file stays valid JSON. It is
never cleared between runs.
"""

import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from models import AuditEntry, AuditToolCall, AuditToolResult, AuditUsage

AUDIT_PATH = Path(
    os.getenv("CAMPUS_CUSTOMS_AUDIT", Path(__file__).resolve().parents[1] / "output" / "audit_trail.json")
)
MAX_RESULT_CHARS = 600
MAX_TEXT_CHARS = 1500

_lock = threading.Lock()

# Card-like numbers and secrets must never land in a log file.
_CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")
_SECRET = re.compile(r"(?i)\b(api[_-]?key|password|secret|token)\b\s*[:=]\s*\S+")


def redact(text: str) -> str:
    text = _CARD.sub("[redacted number]", text)
    return _SECRET.sub(r"\1=[redacted]", text)


def shorten(value: Any, limit: int = MAX_RESULT_CHARS) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    text = redact(text)
    return text if len(text) <= limit else text[: limit - 15] + " …[truncated]"


def append_entry(entry: AuditEntry) -> None:
    block = entry.model_dump_json(indent=2, exclude_none=True).encode()
    with _lock:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not AUDIT_PATH.exists() or AUDIT_PATH.stat().st_size == 0:
            AUDIT_PATH.write_bytes(b"[\n" + block + b"\n]\n")
            return
        with AUDIT_PATH.open("rb+") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 64))
            tail = f.read()
            close = tail.rfind(b"]")
            if close == -1:
                raise ValueError(f"{AUDIT_PATH} doesn't end with ']'; not appending to avoid damaging it")
            close_at = size - len(tail) + close
            f.seek(max(0, close_at - 64))
            before = f.read(close_at - max(0, close_at - 64)).rstrip()
            separator = b"\n" if before.endswith(b"[") else b",\n"
            f.seek(close_at)
            f.write(separator + block + b"\n]\n")
            f.truncate()


class AuditLogger:
    """Writes the entries for one team run. Shared by every agent in that run."""

    def __init__(self, team_run_id: str, ticket_id: int | None = None):
        self.team_run_id = team_run_id
        self.ticket_id = ticket_id
        self.seq = 0

    def log(self, **fields: Any) -> None:
        self.seq += 1
        for key in ("text", "task"):
            if fields.get(key):
                fields[key] = shorten(fields[key], MAX_TEXT_CHARS)
        append_entry(
            AuditEntry(
                timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                team_run_id=self.team_run_id,
                ticket_id=self.ticket_id,
                seq=self.seq,
                **fields,
            )
        )


def tool_call(tool_call_id: str, tool: str, args: Any) -> AuditToolCall:
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            pass
    if isinstance(args, dict):
        args = {k: shorten(v, 300) if isinstance(v, str) else v for k, v in args.items()}
    else:
        args = shorten(args, 300)
    return AuditToolCall(tool_call_id=tool_call_id, tool=tool, args=args)


def tool_result(tool_call_id: str, tool: str, content: Any, is_error: bool) -> AuditToolResult:
    text = shorten(content)
    outcome = "error" if is_error else ("blocked" if text.lstrip('{"').startswith("blocked") else "ok")
    return AuditToolResult(tool_call_id=tool_call_id, tool=tool, outcome=outcome, result=text)


def usage(u: Any) -> AuditUsage:
    return AuditUsage(
        requests=getattr(u, "requests", 0) or 0,
        tool_calls=getattr(u, "tool_calls", 0) or 0,
        input_tokens=getattr(u, "input_tokens", 0) or 0,
        output_tokens=getattr(u, "output_tokens", 0) or 0,
    )

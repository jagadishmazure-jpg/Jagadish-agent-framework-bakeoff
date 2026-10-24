"""What every adapter returns, plus the approval and tracing contract."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from .domain import Ledger
from .pii import mask

Approver = Callable[[str, float], bool]


def deny_all(order_id: str, amount: float) -> bool:
    return False


@dataclass
class Trace:
    spans: list[dict] = field(default_factory=list)

    def add(self, kind: str, name: str, **attrs) -> None:
        self.spans.append({"kind": kind, "name": name, **{k: mask(str(v)) for k, v in attrs.items()}})

    def kinds(self) -> list[str]:
        return [s["kind"] for s in self.spans]


@dataclass
class Outcome:
    final: str
    agents: list[str]
    tool_calls: list[str]
    approvals_asked: list[tuple[str, float]]
    ledger: Ledger
    trace: Trace


class Recorder:
    """Shared bookkeeping used inside each adapter's tool functions."""

    def __init__(self, approver: Approver):
        self.approver = approver
        self.ledger = Ledger()
        self.trace = Trace()
        self.agents: list[str] = ["triage"]
        self.tool_calls: list[str] = []
        self.approvals: list[tuple[str, float]] = []

    def start(self, user_text: str) -> None:
        self.trace.add("input", "user", text=user_text)

    def ask(self, order_id: str, amount: float) -> bool:
        self.approvals.append((order_id, float(amount)))
        ok = bool(self.approver(order_id, float(amount)))
        self.trace.add("approval", "human", order_id=order_id, amount=amount, approved=ok)
        return ok

    def handoff(self, to: str) -> None:
        self.agents.append(to)
        self.trace.add("handoff", to)

    def outcome(self, final: str) -> Outcome:
        self.trace.add("final", self.agents[-1], text=final)
        return Outcome(final, self.agents, self.tool_calls, self.approvals, self.ledger, self.trace)

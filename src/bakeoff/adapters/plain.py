"""Baseline: the support agent as a plain Python loop, with no framework."""

from __future__ import annotations

from ..domain import issue_refund, lookup_order
from ..harness import Approver, Outcome, Recorder
from ..policy import decide

NAME = "plain-python"
DIST = None


def version() -> str:
    return "-"


MAX_TURNS = 8


def available() -> bool:
    return True


def run(user_text: str, approver: Approver) -> Outcome:
    rec = Recorder(approver)
    rec.start(user_text)
    results: list[dict] = []
    for _ in range(MAX_TURNS):
        agent = rec.agents[-1]
        act = decide(agent, user_text, results)
        rec.trace.add("model", agent, action=act["type"])
        if act["type"] == "final":
            return rec.outcome(act["text"])
        if act["type"] == "handoff":
            rec.handoff(act["to"])
            continue
        rec.tool_calls.append(act["name"])
        a = act["args"]
        if act["name"] == "lookup_order":
            res = lookup_order(a["order_id"])
        else:
            res = issue_refund(rec.ledger, a["order_id"], a["amount"], rec.ask(a["order_id"], a["amount"]))
        rec.trace.add("tool", act["name"], args=a, result=res)
        results.append(res)
    return rec.outcome("Stopped: turn limit reached.")

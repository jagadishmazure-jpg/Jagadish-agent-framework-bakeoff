"""LangGraph adapter.

- Model: graph nodes call the shared policy directly; LangGraph orchestrates and needs no model object.
- Handoff: a conditional edge from the triage node to the billing node, with `active` agent kept in state.
- Human approval: native `interrupt()` inside the refund node, with a MemorySaver checkpointer; we resume
  with `Command(resume=<bool>)`.
- Tracing: `stream_mode="updates"` yields one event per node run, which we record as spans.
"""

from __future__ import annotations

import operator
from importlib import metadata
from typing import Annotated, TypedDict

from ..domain import issue_refund, lookup_order
from ..harness import Approver, Outcome, Recorder
from ..policy import decide

NAME = "langgraph"
DIST = "langgraph"


def available() -> bool:
    try:
        import langgraph  # noqa: F401
    except ImportError:
        return False
    return True


def version() -> str:
    return metadata.version(DIST)


class S(TypedDict):
    user: str
    active: str
    results: Annotated[list, operator.add]
    pending: dict
    final: str


def run(user_text: str, approver: Approver) -> Outcome:
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import Command, interrupt

    rec = Recorder(approver)
    rec.start(user_text)

    def agent_node(state: S) -> dict:
        act = decide(state["active"], state["user"], state["results"])
        rec.trace.add("model", state["active"], action=act["type"])
        if act["type"] == "final":
            return {"final": act["text"], "pending": {}}
        if act["type"] == "handoff":
            rec.handoff(act["to"])
            return {"active": act["to"], "pending": {}}
        return {"pending": act}

    def route(state: S) -> str:
        if state.get("final"):
            return END
        p = state.get("pending") or {}
        if not p:
            return "agent"
        return "refund" if p["name"] == "issue_refund" else "lookup"

    def lookup_node(state: S) -> dict:
        a = state["pending"]["args"]
        rec.tool_calls.append("lookup_order")
        res = lookup_order(a["order_id"])
        rec.trace.add("tool", "lookup_order", args=a, result=res)
        return {"results": [res], "pending": {}}

    def refund_node(state: S) -> dict:
        a = state["pending"]["args"]
        ok = interrupt({"order_id": a["order_id"], "amount": a["amount"]})
        rec.tool_calls.append("issue_refund")
        res = issue_refund(rec.ledger, a["order_id"], a["amount"], approved=bool(ok))
        rec.trace.add("tool", "issue_refund", args=a, result=res)
        return {"results": [res], "pending": {}}

    g = StateGraph(S)
    g.add_node("agent", agent_node)
    g.add_node("lookup", lookup_node)
    g.add_node("refund", refund_node)
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", route, ["agent", "lookup", "refund", END])
    g.add_edge("lookup", "agent")
    g.add_edge("refund", "agent")
    app = g.compile(checkpointer=MemorySaver())
    cfg = {"configurable": {"thread_id": "t1"}, "recursion_limit": 16}

    inp: object = {"user": user_text, "active": "triage", "results": [], "pending": {}, "final": ""}
    while True:
        interrupted = None
        for ev in app.stream(inp, cfg, stream_mode="updates"):
            for node, val in ev.items():
                if node == "__interrupt__":
                    interrupted = val[0].value
                else:
                    rec.trace.add("lg:node", node)
        if interrupted is None:
            break
        inp = Command(resume=rec.ask(interrupted["order_id"], interrupted["amount"]))
    return rec.outcome(app.get_state(cfg).values.get("final") or "Stopped.")

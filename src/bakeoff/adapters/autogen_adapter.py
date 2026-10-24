"""AutoGen (AgentChat 0.7) adapter, running offline.

- Model: a custom `ChatCompletionClient` that calls the shared policy. No API key and no network.
- Handoff: a native `Swarm` team; triage calls the generated `transfer_to_billing` tool.
- Human approval: the documented Swarm pattern. Before a refund, billing hands off to "user", and
  `HandoffTermination(target="user")` stops the run. We ask the approver and resume the team with a
  `HandoffMessage` from the user carrying APPROVED or DENIED. The client turns DENIED into the same
  "needs approval" result the other frameworks see, so the shared policy is unchanged.
- Tracing: every message and event from `run_stream` is recorded as a span.
"""

from __future__ import annotations

import asyncio
import json
from importlib import metadata

from ..domain import issue_refund, lookup_order
from ..harness import Approver, Outcome, Recorder
from ..policy import decide

NAME = "autogen"
DIST = "autogen-agentchat"


def available() -> bool:
    try:
        import autogen_agentchat  # noqa: F401
    except ImportError:
        return False
    return True


def version() -> str:
    return metadata.version(DIST)


def _read(messages) -> tuple[str, str, list[dict], str | None]:
    from autogen_core.models import FunctionExecutionResultMessage, SystemMessage, UserMessage

    agent, user, results, decision = "triage", "", [], None
    for m in messages:
        if isinstance(m, SystemMessage) and "agent=" in m.content:
            agent = m.content.split("agent=")[1].split()[0]
        elif isinstance(m, UserMessage) and isinstance(m.content, str):
            if m.content in ("APPROVED", "DENIED"):
                decision = m.content
            elif not user:
                user = m.content
        elif isinstance(m, FunctionExecutionResultMessage):
            for r in m.content:
                try:
                    out = json.loads(r.content)
                except (ValueError, TypeError):
                    continue
                if isinstance(out, dict) and ("status" in out or "error" in out or "refunded" in out):
                    results.append(out)
    return agent, user, results, decision


def run(user_text: str, approver: Approver) -> Outcome:
    return asyncio.run(_run(user_text, approver))


async def _run(user_text: str, approver: Approver) -> Outcome:
    from autogen_agentchat.agents import AssistantAgent
    from autogen_agentchat.conditions import HandoffTermination, MaxMessageTermination, TextMessageTermination
    from autogen_agentchat.messages import HandoffMessage
    from autogen_agentchat.teams import Swarm
    from autogen_core import FunctionCall
    from autogen_core.models import ChatCompletionClient, CreateResult, ModelInfo, RequestUsage

    rec = Recorder(approver)
    rec.start(user_text)
    pending: dict = {}
    n = {"i": 0}

    class PolicyClient(ChatCompletionClient):
        async def create(
            self, messages, *, tools=(), tool_choice="auto", json_output=None, extra_create_args=None, cancellation_token=None
        ):
            agent, user, results, decision = _read(messages)
            if decision == "DENIED" and not any("refunded" in r or "approval" in r.get("error", "") for r in results):
                results = [*results, {"error": "refund needs human approval"}]
            act = decide(agent, user, results)
            rec.trace.add("model", agent, action=act["type"])
            n["i"] += 1
            usage = RequestUsage(prompt_tokens=0, completion_tokens=0)
            if act["type"] == "final":
                return CreateResult(finish_reason="stop", content=act["text"], usage=usage, cached=False)
            if act["type"] == "handoff":
                call = FunctionCall(id=f"c{n['i']}", name="transfer_to_billing", arguments="{}")
            elif act["name"] == "issue_refund" and decision is None:
                pending.update(act["args"])
                call = FunctionCall(id=f"c{n['i']}", name="transfer_to_user", arguments="{}")
            else:
                call = FunctionCall(id=f"c{n['i']}", name=act["name"], arguments=json.dumps(act["args"]))
            return CreateResult(finish_reason="function_calls", content=[call], usage=usage, cached=False)

        def create_stream(self, *a, **kw):
            raise NotImplementedError

        async def close(self):
            pass

        def actual_usage(self):
            return RequestUsage(prompt_tokens=0, completion_tokens=0)

        def total_usage(self):
            return RequestUsage(prompt_tokens=0, completion_tokens=0)

        def count_tokens(self, messages, *, tools=()):
            return 0

        def remaining_tokens(self, messages, *, tools=()):
            return 10**6

        @property
        def capabilities(self):
            return self.model_info

        @property
        def model_info(self) -> ModelInfo:
            return ModelInfo(vision=False, function_calling=True, json_output=False, family="unknown", structured_output=False)

    async def lookup_order_tool(order_id: str) -> str:
        """Look up an order by id."""
        rec.tool_calls.append("lookup_order")
        res = lookup_order(order_id)
        rec.trace.add("tool", "lookup_order", args={"order_id": order_id}, result=res)
        return json.dumps(res)

    async def issue_refund_tool(order_id: str, amount: float) -> str:
        """Refund an order. Only reachable after the user approved."""
        rec.tool_calls.append("issue_refund")
        res = issue_refund(rec.ledger, order_id, amount, approved=True)
        rec.trace.add("tool", "issue_refund", args={"order_id": order_id, "amount": amount}, result=res)
        return json.dumps(res)

    from autogen_core.tools import FunctionTool

    t_lookup = FunctionTool(lookup_order_tool, description="Look up an order by id.", name="lookup_order")
    t_refund = FunctionTool(issue_refund_tool, description="Refund an order.", name="issue_refund")
    client = PolicyClient()
    triage = AssistantAgent("triage", model_client=client, tools=[t_lookup], handoffs=["billing"], system_message="agent=triage")
    billing = AssistantAgent(
        "billing", model_client=client, tools=[t_lookup, t_refund], handoffs=["user"], system_message="agent=billing"
    )
    stop = (
        HandoffTermination(target="user")
        | TextMessageTermination("triage")
        | TextMessageTermination("billing")
        | MaxMessageTermination(24)
    )
    team = Swarm([triage, billing], termination_condition=stop)

    task: object = user_text
    final = "Stopped."
    while True:
        handed_to_user = False
        async for ev in team.run_stream(task=task):
            kind = type(ev).__name__
            rec.trace.add("ag:" + kind, getattr(ev, "source", ""))
            if isinstance(ev, HandoffMessage):
                if ev.target == "user":
                    handed_to_user = True
                elif ev.target != rec.agents[-1]:
                    rec.handoff(ev.target)
            if kind == "TextMessage" and ev.source in ("triage", "billing"):
                final = ev.content
        if not handed_to_user:
            break
        ok = rec.ask(pending["order_id"], pending["amount"])
        if not ok:
            rec.tool_calls.append("issue_refund")
        task = HandoffMessage(source="user", target="billing", content="APPROVED" if ok else "DENIED")
    return rec.outcome(final)

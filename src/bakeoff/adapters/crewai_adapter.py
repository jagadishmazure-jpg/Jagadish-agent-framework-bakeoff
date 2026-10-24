"""CrewAI adapter, running offline.

- Model: a custom `crewai.BaseLLM` subclass that calls the shared policy and answers in CrewAI's
  ReAct text format (Thought / Action / Action Input / Final Answer). Telemetry and tracing upload are
  turned off with environment variables before import.
- Handoff: native delegation. Triage has `allow_delegation=True` and calls CrewAI's built-in
  "Delegate work to coworker" tool with coworker="billing". Billing's answer comes back to triage as
  an observation, and triage returns it as the final answer.
- Human approval: CrewAI has no pause-and-resume for a single tool call here (Task `human_input` reviews
  the final output on stdin). So the refund tool calls the approver itself, before any side effect.
  The comparison matrix marks this as an in-tool callback, not native HITL.
- Tracing: CrewAI's event bus (tool usage and LLM call events) is recorded as spans.
"""

from __future__ import annotations

import json
import os
import re
from importlib import metadata

from ..domain import issue_refund, lookup_order
from ..harness import Approver, Outcome, Recorder
from ..policy import decide

NAME = "crewai"
DIST = "crewai"
DELEGATE = "Delegate work to coworker"


def available() -> bool:
    try:
        import crewai  # noqa: F401
    except ImportError:
        return False
    return True


def version() -> str:
    return metadata.version(DIST)


def _offline_env() -> None:
    os.environ["CREWAI_TRACING_ENABLED"] = "false"
    os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
    os.environ["OTEL_SDK_DISABLED"] = "true"


def _read(messages) -> tuple[str, str, list[dict], str | None]:
    msgs = messages if isinstance(messages, list) else [{"role": "user", "content": messages}]
    system = " ".join(m["content"] for m in msgs if m.get("role") == "system")
    m = re.search(r"You are (\w+)\.", system)
    agent = m.group(1) if m else "triage"
    first_user = next((x["content"] for x in msgs if x.get("role") == "user"), "")
    um = re.search(r"CUSTOMER SAYS: (.*?) :END", first_user, re.S)
    user = um.group(1).strip() if um else ""
    results, delegated = [], None
    for x in msgs:
        if x.get("role") != "assistant":
            continue
        for obs in re.findall(r"Observation: (.*)", x["content"], re.S):
            obs = obs.strip()
            if f"Action: {DELEGATE}" in x["content"]:
                delegated = obs
                continue
            try:
                r = json.loads(obs)
            except ValueError:
                continue
            if isinstance(r, dict):
                results.append(r)
    return agent, user, results, delegated


def run(user_text: str, approver: Approver) -> Outcome:
    _offline_env()
    from crewai import Agent, BaseLLM, Crew, Task
    from crewai.events import ToolUsageFinishedEvent, crewai_event_bus
    from crewai.tools import tool

    rec = Recorder(approver)
    rec.start(user_text)

    class PolicyLLM(BaseLLM):
        def call(
            self,
            messages,
            tools=None,
            callbacks=None,
            available_functions=None,
            from_task=None,
            from_agent=None,
            response_model=None,
        ):
            agent, user, results, delegated = _read(messages)
            if delegated is not None:
                rec.trace.add("model", agent, action="final")
                return f"Thought: billing answered\nFinal Answer: {delegated}"
            act = decide(agent, user, results)
            rec.trace.add("model", agent, action=act["type"])
            if act["type"] == "final":
                return f"Thought: I now know the final answer\nFinal Answer: {act['text']}"
            if act["type"] == "handoff":
                rec.handoff(act["to"])
                args = {"task": f"CUSTOMER SAYS: {user} :END", "context": json.dumps(results), "coworker": act["to"]}
                return f"Thought: billing owns refunds\nAction: {DELEGATE}\nAction Input: {json.dumps(args)}"
            return f"Thought: next step\nAction: {act['name']}\nAction Input: {json.dumps(act['args'])}"

        def supports_function_calling(self) -> bool:
            return False

    @tool("lookup_order")
    def lookup_order_tool(order_id: str) -> str:
        """Look up an order by id."""
        rec.tool_calls.append("lookup_order")
        res = lookup_order(order_id)
        rec.trace.add("tool", "lookup_order", args={"order_id": order_id}, result=res)
        return json.dumps(res)

    @tool("issue_refund")
    def issue_refund_tool(order_id: str, amount: float) -> str:
        """Refund an order. Asks a human first."""
        rec.tool_calls.append("issue_refund")
        res = issue_refund(rec.ledger, order_id, float(amount), approved=rec.ask(order_id, float(amount)))
        rec.trace.add("tool", "issue_refund", args={"order_id": order_id, "amount": amount}, result=res)
        return json.dumps(res)

    llm = PolicyLLM(model="policy-fake")
    billing = Agent(
        role="billing", goal="Handle refunds", backstory="Billing desk", llm=llm, tools=[lookup_order_tool, issue_refund_tool]
    )
    triage = Agent(
        role="triage",
        goal="Answer order questions",
        backstory="Front desk",
        llm=llm,
        tools=[lookup_order_tool],
        allow_delegation=True,
    )
    task = Task(description=f"CUSTOMER SAYS: {user_text} :END", expected_output="A reply to the customer", agent=triage)

    def on_tool(source, event):
        rec.trace.add("crewai:tool", getattr(event, "tool_name", ""))

    with crewai_event_bus.scoped_handlers():
        crewai_event_bus.on(ToolUsageFinishedEvent)(on_tool)
        result = Crew(agents=[triage, billing], tasks=[task], verbose=False).kickoff()
    return rec.outcome(str(result.raw).strip())

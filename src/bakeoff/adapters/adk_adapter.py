"""Google ADK adapter, running offline.

- Model: a custom `BaseLlm` subclass that calls the shared policy. No API key and no network.
- Handoff: native `sub_agents=[billing]`; the model calls ADK's `transfer_to_agent`.
- Human approval: native `FunctionTool(require_confirmation=True)`. The run pauses with an
  `adk_request_confirmation` call; we answer it with a FunctionResponse {"confirmed": bool} and resume.
- Tracing: every Event from `run_async` (author, calls, responses) is recorded as a span.
- State: InMemorySessionService.
"""

from __future__ import annotations

import asyncio
from importlib import metadata

from ..domain import issue_refund, lookup_order
from ..harness import Approver, Outcome, Recorder
from ..policy import decide

NAME = "google-adk"
DIST = "google-adk"
CONFIRM = "adk_request_confirmation"


def available() -> bool:
    try:
        import google.adk  # noqa: F401
    except ImportError:
        return False
    return True


def version() -> str:
    return metadata.version(DIST)


def _read(req) -> tuple[str, str, list[dict]]:
    sys = req.config.system_instruction if req.config else ""
    sys = sys if isinstance(sys, str) else str(sys)
    agent = sys.split("agent=")[1].split()[0] if "agent=" in sys else "triage"
    user, results = "", []
    for c in req.contents or []:
        for p in c.parts or []:
            if c.role == "user" and p.text and not user and "agent=" not in p.text:
                user = p.text
            fr = p.function_response
            if fr and fr.name in ("lookup_order", "issue_refund"):
                r = dict(fr.response or {})
                r = r.get("result", r) if isinstance(r.get("result"), dict) else r
                if fr.name == "issue_refund" and "error" in r and "reject" in str(r["error"]).lower():
                    r = {"error": "refund needs human approval"}
                results.append(r)
    return agent, user, results


def run(user_text: str, approver: Approver) -> Outcome:
    return asyncio.run(_run(user_text, approver))


async def _run(user_text: str, approver: Approver) -> Outcome:
    from google.adk.agents import LlmAgent
    from google.adk.models.base_llm import BaseLlm
    from google.adk.models.llm_response import LlmResponse
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.adk.tools import FunctionTool
    from google.genai import types

    rec = Recorder(approver)
    rec.start(user_text)

    class PolicyLlm(BaseLlm):
        async def generate_content_async(self, llm_request, stream: bool = False):
            agent, user, results = _read(llm_request)
            act = decide(agent, user, results)
            rec.trace.add("model", agent, action=act["type"])
            if act["type"] == "final":
                part = types.Part(text=act["text"])
            elif act["type"] == "handoff":
                part = types.Part(function_call=types.FunctionCall(name="transfer_to_agent", args={"agent_name": act["to"]}))
            else:
                part = types.Part(function_call=types.FunctionCall(name=act["name"], args=act["args"]))
            yield LlmResponse(content=types.Content(role="model", parts=[part]))

    def lookup_order_fn(order_id: str) -> dict:
        """Look up an order by id."""
        rec.tool_calls.append("lookup_order")
        res = lookup_order(order_id)
        rec.trace.add("tool", "lookup_order", args={"order_id": order_id}, result=res)
        return res

    def issue_refund_fn(order_id: str, amount: float) -> dict:
        """Refund an order. Requires human confirmation."""
        rec.tool_calls.append("issue_refund")
        res = issue_refund(rec.ledger, order_id, amount, approved=True)
        rec.trace.add("tool", "issue_refund", args={"order_id": order_id, "amount": amount}, result=res)
        return res

    lookup_order_fn.__name__ = "lookup_order"
    issue_refund_fn.__name__ = "issue_refund"
    llm = PolicyLlm(model="policy-fake")
    billing = LlmAgent(
        name="billing",
        model=llm,
        instruction="agent=billing",
        description="Handles refunds.",
        tools=[FunctionTool(lookup_order_fn), FunctionTool(issue_refund_fn, require_confirmation=True)],
    )
    triage = LlmAgent(
        name="triage", model=llm, instruction="agent=triage", tools=[FunctionTool(lookup_order_fn)], sub_agents=[billing]
    )
    svc = InMemorySessionService()
    runner = Runner(app_name="bakeoff", agent=triage, session_service=svc)
    session = await svc.create_session(app_name="bakeoff", user_id="u1")

    msg = types.Content(role="user", parts=[types.Part(text=user_text)])
    final = "Stopped."
    for _ in range(4):
        pending = []
        async for ev in runner.run_async(user_id="u1", session_id=session.id, new_message=msg):
            rec.trace.add("adk:event", ev.author)
            if ev.actions and ev.actions.transfer_to_agent and ev.actions.transfer_to_agent != rec.agents[-1]:
                rec.handoff(ev.actions.transfer_to_agent)
            for p in ev.content.parts if ev.content and ev.content.parts else []:
                if p.function_call and p.function_call.name == CONFIRM:
                    pending.append(p.function_call)
                if p.text and ev.author in ("triage", "billing"):
                    final = p.text
        if not pending:
            break
        parts = []
        for fc in pending:
            orig = fc.args["originalFunctionCall"]["args"]
            ok = rec.ask(orig["order_id"], orig["amount"])
            if not ok:
                rec.tool_calls.append("issue_refund")
            parts.append(types.Part(function_response=types.FunctionResponse(id=fc.id, name=CONFIRM, response={"confirmed": ok})))
        msg = types.Content(role="user", parts=parts)
    return rec.outcome(final)

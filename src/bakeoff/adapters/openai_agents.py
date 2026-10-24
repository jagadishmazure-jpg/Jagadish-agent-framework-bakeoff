"""OpenAI Agents SDK adapter, running offline.

- Model: a custom `agents.Model` subclass that calls the shared policy. No API key and no network.
- Handoff: the SDK's native `handoffs=[billing]`; the model calls the generated transfer tool.
- Human approval: native `needs_approval=True` on `issue_refund`; the run pauses with an interruption,
  and we approve or reject it from the approver, then resume from the saved RunState.
- Tracing: the default exporter is replaced with an in-process TracingProcessor, so nothing is uploaded.
"""

from __future__ import annotations

import asyncio
import json
from importlib import metadata

from ..domain import issue_refund, lookup_order
from ..harness import Approver, Outcome, Recorder
from ..policy import decide

NAME = "openai-agents"
DIST = "openai-agents"


def available() -> bool:
    try:
        import agents  # noqa: F401
    except ImportError:
        return False
    return True


def version() -> str:
    return metadata.version(DIST)


def _user_and_results(items) -> tuple[str, list[dict]]:
    user, results, names = "", [], {}
    for it in items if isinstance(items, list) else [{"role": "user", "content": items}]:
        d = it if isinstance(it, dict) else it.model_dump()
        if d.get("role") == "user" and not user:
            c = d["content"]
            user = c if isinstance(c, str) else " ".join(p.get("text", "") for p in c)
        if d.get("type") == "function_call":
            names[d["call_id"]] = d["name"]
        if d.get("type") == "function_call_output":
            try:
                out = json.loads(d["output"])
            except (ValueError, TypeError):
                # A rejected approval comes back as plain text in place of the tool output.
                if names.get(d.get("call_id")) == "issue_refund":
                    results.append({"error": "refund needs human approval"})
                continue
            if isinstance(out, dict) and ("status" in out or "error" in out or "refunded" in out):
                results.append(out)
    return user, results


def run(user_text: str, approver: Approver) -> Outcome:
    return asyncio.run(_run(user_text, approver))


async def _run(user_text: str, approver: Approver) -> Outcome:
    from agents import Agent, Model, ModelResponse, Runner, TracingProcessor, Usage, function_tool, set_trace_processors
    from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText

    rec = Recorder(approver)
    rec.start(user_text)
    counter = {"n": 0}

    class Spans(TracingProcessor):
        def on_trace_start(self, trace):
            pass

        def on_trace_end(self, trace):
            pass

        def on_span_start(self, span):
            pass

        def on_span_end(self, span):
            data = span.span_data
            if data.type == "handoff" and data.to_agent:
                rec.handoff(data.to_agent)
            rec.trace.add("sdk:" + data.type, getattr(data, "name", "") or getattr(data, "to_agent", "") or "")

        def shutdown(self):
            pass

        def force_flush(self):
            pass

    set_trace_processors([Spans()])

    class PolicyModel(Model):
        async def get_response(self, system_instructions, input, model_settings, tools, output_schema, handoffs, tracing, **kw):
            agent = (system_instructions or "agent=triage").split("agent=")[1].split()[0]
            user, results = _user_and_results(input)
            act = decide(agent, user, results)
            rec.trace.add("model", agent, action=act["type"])
            counter["n"] += 1
            cid = f"call_{counter['n']}"
            if act["type"] == "final":
                out = ResponseOutputMessage(
                    id=f"msg_{counter['n']}",
                    type="message",
                    role="assistant",
                    status="completed",
                    content=[ResponseOutputText(type="output_text", text=act["text"], annotations=[])],
                )
            else:
                name = "transfer_to_billing" if act["type"] == "handoff" else act["name"]
                args = {} if act["type"] == "handoff" else act["args"]
                out = ResponseFunctionToolCall(
                    id=f"fc_{counter['n']}", call_id=cid, type="function_call", name=name, arguments=json.dumps(args)
                )
            return ModelResponse(output=[out], usage=Usage(), response_id=None)

        def stream_response(self, *a, **kw):
            raise NotImplementedError

    @function_tool
    def lookup_order_tool(order_id: str) -> str:
        """Look up an order by id."""
        rec.tool_calls.append("lookup_order")
        res = lookup_order(order_id)
        rec.trace.add("tool", "lookup_order", args={"order_id": order_id}, result=res)
        return json.dumps(res)

    @function_tool(needs_approval=True)
    def issue_refund_tool(order_id: str, amount: float) -> str:
        """Refund an order. Requires human approval."""
        rec.tool_calls.append("issue_refund")
        res = issue_refund(rec.ledger, order_id, amount, approved=True)
        rec.trace.add("tool", "issue_refund", args={"order_id": order_id, "amount": amount}, result=res)
        return json.dumps(res)

    lookup_order_tool.name = "lookup_order"
    issue_refund_tool.name = "issue_refund"
    model = PolicyModel()
    billing = Agent(name="billing", instructions="agent=billing", model=model, tools=[lookup_order_tool, issue_refund_tool])
    triage = Agent(name="triage", instructions="agent=triage", model=model, tools=[lookup_order_tool], handoffs=[billing])

    result = await Runner.run(triage, user_text, max_turns=8)
    while result.interruptions:
        state = result.to_state()
        for item in result.interruptions:
            args = json.loads(item.arguments or "{}")
            if rec.ask(args["order_id"], args["amount"]):
                state.approve(item)
            else:
                state.reject(item)
                rec.tool_calls.append("issue_refund")
        result = await Runner.run(triage, state, max_turns=8)
    return rec.outcome(str(result.final_output))

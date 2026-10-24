"""The deterministic stand-in model, shared by every framework.

It is a pure function from (agent name, user text, tool results so far) to the next action, so every
adapter drives the same decisions. The frameworks differ only in how they wire it up.

Actions:
  {"type": "tool", "name": "lookup_order" | "issue_refund", "args": {...}}
  {"type": "handoff", "to": "billing"}
  {"type": "final", "text": "..."}
"""

from __future__ import annotations

from .domain import parse_request


def decide(agent: str, user_text: str, results: list[dict]) -> dict:
    req = parse_request(user_text)
    looked = next((r for r in results if "status" in r or ("error" in r and "not found" in r["error"])), None)
    if req["order_id"] is None:
        return {"type": "final", "text": "Please share your order number (it looks like BW-1234)."}
    if looked is None:
        return {"type": "tool", "name": "lookup_order", "args": {"order_id": req["order_id"]}}
    if "error" in looked:
        return {"type": "final", "text": f"I could not find order {req['order_id']}. Please check the number."}
    if not req["refund"]:
        return {"type": "final", "text": f"Order {req['order_id']} ({looked['item']}) is {looked['status']}."}
    if agent == "triage":
        return {"type": "handoff", "to": "billing"}
    refund_res = next((r for r in results if "refunded" in r or ("error" in r and "not found" not in r["error"])), None)
    if refund_res is None:
        amount = req["amount"] if req["amount"] is not None else looked["total"]
        return {"type": "tool", "name": "issue_refund", "args": {"order_id": req["order_id"], "amount": amount}}
    if refund_res.get("ok"):
        return {"type": "final", "text": f"Refunded {refund_res['refunded']:.2f} for order {req['order_id']}."}
    if "approval" in refund_res["error"]:
        return {"type": "final", "text": "A team member declined this refund, so no money was moved."}
    return {"type": "final", "text": f"I cannot refund that amount: {refund_res['error']}."}

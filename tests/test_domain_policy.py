import pytest

from bakeoff.domain import Ledger, issue_refund, lookup_order, parse_request
from bakeoff.policy import decide


def test_lookup_known_and_unknown():
    assert lookup_order("BW-1001")["status"] == "shipped"
    assert "error" in lookup_order("BW-0000")


def test_notes_are_marked_untrusted():
    r = lookup_order("BW-1004")
    assert "untrusted_notes" in r and "notes" not in r


@pytest.mark.parametrize(
    "oid,amt,ok,expect",
    [
        ("BW-1002", 20, True, True),
        ("BW-1002", 20, False, False),
        ("BW-1002", 50, True, False),
        ("BW-1003", 250, True, False),
        ("BW-9999", 1, True, False),
    ],
)
def test_refund_rules(oid, amt, ok, expect):
    led = Ledger()
    res = issue_refund(led, oid, amt, approved=ok)
    assert bool(res.get("ok")) is expect
    assert bool(led.refunds) is expect


def test_parse_request_ignores_order_digits():
    assert parse_request("refund BW-1002") == {"order_id": "BW-1002", "refund": True, "amount": None}
    assert parse_request("refund $12.50 on BW-1002")["amount"] == 12.5


def test_policy_sequence_for_refund():
    t = "refund 20.00 on BW-1002"
    assert decide("triage", t, []) == {"type": "tool", "name": "lookup_order", "args": {"order_id": "BW-1002"}}
    looked = [lookup_order("BW-1002")]
    assert decide("triage", t, looked) == {"type": "handoff", "to": "billing"}
    assert decide("billing", t, looked)["name"] == "issue_refund"


def test_policy_never_takes_amount_from_tool_output():
    t = "refund for BW-1004"
    act = decide("billing", t, [lookup_order("BW-1004")])
    assert act["args"]["amount"] == 19.99


def test_policy_asks_for_order_number():
    assert decide("triage", "help", [])["type"] == "final"

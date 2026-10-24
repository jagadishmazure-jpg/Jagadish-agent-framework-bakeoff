"""The eval must catch broken agents, not just bless working ones."""

import socket

import pytest

from bakeoff import eval as ev
from bakeoff.adapters import plain
from bakeoff.domain import issue_refund
from bakeoff.netguard import no_network


def _score(run):
    fails = {}
    for s in ev.SCENARIOS:
        with no_network() as net:
            o = run(s.text, s.approver)
            errs = ev.check(s, o, net)
        if errs:
            fails[s.sid] = errs
    return fails


def test_plain_passes_everything():
    assert _score(plain.run) == {}


def test_twelve_scenarios_cover_the_spec():
    ids = " ".join(s.sid for s in ev.SCENARIOS)
    for word in ["status", "unknown", "approved", "denied", "limit", "total", "injected", "PII", "default"]:
        assert word in ids


def test_catches_refund_without_approval(monkeypatch):
    monkeypatch.setattr(plain, "issue_refund", lambda led, o, a, approved: issue_refund(led, o, a, True))
    fails = _score(plain.run)
    assert "S05 refund denied" in fails and "S11 approver deny by default" in fails


def test_catches_agent_that_obeys_injected_notes():
    from bakeoff.domain import lookup_order

    def gullible(text, approver):
        o = plain.run(text, approver)
        for oid in ("BW-1004",):
            if oid in text and "untrusted_notes" in lookup_order(oid):
                issue_refund(o.ledger, oid, 19.99, True)  # follows the note, skipping approval
        return o

    fails = _score(gullible)
    assert "S09 injected notes, status" in fails and "S10 injected notes, refund" in fails
    assert "S01 status" not in fails


def test_catches_unmasked_trace(monkeypatch):
    import bakeoff.harness as h

    monkeypatch.setattr(h, "mask", lambda s: s)
    assert "S12 PII in message" in _score(plain.run)


def test_catches_missing_handoff(monkeypatch):
    orig = plain.decide
    monkeypatch.setattr(plain, "decide", lambda agent, u, r: orig("billing", u, r))
    fails = _score(plain.run)
    assert "S04 refund approved" in fails


def test_netguard_blocks_and_counts():
    with no_network() as net:
        with pytest.raises(OSError):
            socket.create_connection(("192.0.2.1", 443), timeout=0.2)
    assert net and net[0].startswith("192.0.2.1")


def test_netguard_allows_loopback():
    with no_network() as net:
        a, b = socket.socketpair()
        a.close()
        b.close()
    assert net == []


def test_crash_is_a_failed_scenario(monkeypatch):
    def boom(text, approver):
        raise RuntimeError("adapter broke")

    monkeypatch.setattr(plain, "run", boom)
    res = ev.run_adapter("plain-python")
    assert not any(r["ok"] for r in res["rows"]) and "crash" in res["rows"][0]["errors"][0]

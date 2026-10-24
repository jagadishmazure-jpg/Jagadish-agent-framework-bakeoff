"""Every framework adapter, run in its own pinned env, must pass the same 12 scenarios offline.

Locally a missing env is skipped. In CI, BAKEOFF_REQUIRE_ALL=1 turns a missing env into a failure.
"""

import os

import pytest

from bakeoff.eval import ADAPTERS, SCENARIOS
from bakeoff.runner import python_for, run_one

_CACHE: dict = {}


def _res(name):
    if name not in _CACHE:
        _CACHE[name] = run_one(name)
    return _CACHE[name]


@pytest.fixture(params=list(ADAPTERS))
def result(request):
    name = request.param
    if python_for(name) is None:
        if os.environ.get("BAKEOFF_REQUIRE_ALL") == "1":
            pytest.fail(f"env for {name} missing")
        pytest.skip(f"no env for {name}")
    return _res(name)


def test_adapter_runs(result):
    assert result["available"], result


def test_adapter_passes_all_scenarios(result):
    bad = {r["id"]: r["errors"] for r in result["rows"] if not r["ok"]}
    assert bad == {} and len(result["rows"]) == len(SCENARIOS)


def test_adapter_makes_no_network_attempts(result):
    assert sum(r["net"] for r in result["rows"]) == 0


def test_adapter_moves_money_only_in_approved_scenarios(result):
    # Same tool-call count on the read-only scenarios for every framework.
    by = {r["id"]: r for r in result["rows"]}
    assert by["S03 no order id"]["tool_calls"] == 0
    assert by["S01 status"]["tool_calls"] == 1


def test_adapter_emits_framework_trace_spans(result):
    if result["adapter"] == "plain-python":
        pytest.skip("baseline has no framework tracer")
    assert sum(r["fw_spans"] for r in result["rows"]) > 0


def test_pinned_version_matches_requirements(result):
    from pathlib import Path

    if result["adapter"] == "plain-python":
        return
    root = Path(__file__).resolve().parents[1]
    dist = {"autogen": "autogen-agentchat"}.get(result["adapter"], result["adapter"])
    req = (root / "requirements" / f"{result['adapter']}.txt").read_text()
    assert f"{dist}=={result['version']}" in req
    assert f'"{dist}=={result["version"]}"' in (root / "pyproject.toml").read_text()


def test_results_are_deterministic():
    a = run_one("plain-python")
    b = run_one("plain-python")
    strip = lambda r: [{k: v for k, v in x.items() if k != "ms"} for x in r["rows"]]  # noqa: E731
    assert strip(a) == strip(b)

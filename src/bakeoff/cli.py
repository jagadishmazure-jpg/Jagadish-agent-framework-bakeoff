"""`bakeoff demo` prints every generated table. `all_blocks()` feeds scripts/render_docs.py."""

from __future__ import annotations

import sys

from .eval import SCENARIOS
from .runner import adapter_loc, run_all

# How each adapter wires the four shared concerns. Each cell names the mechanism the adapter really
# uses; tests/test_matrix_claims.py checks the code for the API named here.
FEATURES = {
    "plain-python": ("function returns next agent", "own Trace list", "in-tool callback", "local variables", "-"),
    "openai-agents": (
        "native `handoffs=[...]`",
        "custom TracingProcessor (SDK spans)",
        "native `needs_approval` + RunState resume",
        "RunState (serialisable)",
        "OpenAI Agents SDK",
    ),
    "google-adk": (
        "native `sub_agents` + transfer_to_agent",
        "Event stream",
        "native `require_confirmation` + resume",
        "InMemorySessionService",
        "Google ADK",
    ),
    "crewai": (
        "native delegation tool",
        "event bus (tool events)",
        "in-tool callback (no per-tool pause)",
        "crew/task context",
        "CrewAI",
    ),
    "autogen": (
        "native Swarm handoffs",
        "run_stream messages/events",
        "Swarm handoff to user + resume",
        "team message thread",
        "AutoGen AgentChat",
    ),
    "langgraph": (
        "conditional edge",
        "stream_mode=updates",
        "native `interrupt()` + Command(resume)",
        "checkpointer (MemorySaver)",
        "LangGraph",
    ),
}
MARKERS = {
    "openai-agents": ["handoffs=[billing]", "needs_approval=True", "TracingProcessor", "to_state()"],
    "google-adk": ["sub_agents=[billing]", "require_confirmation=True", "run_async", "InMemorySessionService"],
    "crewai": ["allow_delegation=True", "crewai_event_bus", "rec.ask("],
    "autogen": ["Swarm(", 'HandoffTermination(target="user")', "run_stream", "HandoffMessage("],
    "langgraph": ["add_conditional_edges", "interrupt(", "Command(resume=", "MemorySaver()"],
    "plain-python": ["rec.ask(", "rec.handoff("],
}


def _sum(rows, k):
    return sum(r[k] for r in rows)


def blocks(results: list[dict]) -> dict[str, str]:
    base = next(r for r in results if r["adapter"] == "plain-python")
    bt = _sum(base["rows"], "tool_calls")
    m = [
        "| framework | version | scenarios passed | tool calls | extra vs plain | model calls | framework trace spans | net attempts | adapter LOC |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        if not r.get("available"):
            m.append(
                f"| {r['adapter']} | - | built, not run ({r.get('reason')}) | - | - | - | - | - | {adapter_loc(r['adapter'])} |"
            )
            continue
        rows = r["rows"]
        tc = _sum(rows, "tool_calls")
        m.append(
            f"| {r['adapter']} | {r['version']} | {sum(x['ok'] for x in rows)} / {len(rows)} | {tc} | {tc - bt:+d} | "
            f"{_sum(rows, 'model_calls')} | {_sum(rows, 'fw_spans')} | {_sum(rows, 'net')} | {adapter_loc(r['adapter'])} |"
        )
    f = ["| framework | handoff | tracing | human approval | state |", "| --- | --- | --- | --- | --- |"]
    for name, (h, t, a, s, _) in FEATURES.items():
        f.append(f"| {name} | {h} | {t} | {a} | {s} |")
    names = [r["adapter"] for r in results]
    sc = ["| scenario | " + " | ".join(names) + " |", "| --- |" + " --- |" * len(names)]
    for i, s in enumerate(SCENARIOS):
        cells = []
        for r in results:
            if not r.get("available"):
                cells.append("not run")
            else:
                x = r["rows"][i]
                cells.append(f"{'pass' if x['ok'] else 'FAIL'} ({x['tool_calls']} tools)")
        sc.append(f"| {s.sid} | " + " | ".join(cells) + " |")
    return {"matrix": "\n".join(m), "features": "\n".join(f), "scenarios": "\n".join(sc)}


def all_blocks() -> dict[str, str]:
    return blocks(run_all())


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv or argv[0] != "demo":
        print("usage: bakeoff demo")
        return 2
    for name, text in all_blocks().items():
        print(f"## {name}\n\n{text}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

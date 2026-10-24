# Results

Generated from a fresh run by `python scripts/render_docs.py`. CI fails on drift. Deterministic: scripted model, fixed data, no timings.

<!-- BEGIN:matrix -->
| framework | version | scenarios passed | tool calls | extra vs plain | model calls | framework trace spans | net attempts | adapter LOC |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| plain-python | - | 12 / 12 | 18 | +0 | 37 | 0 | 0 | 33 |
| openai-agents | 0.24.0 | 12 / 12 | 18 | +0 | 37 | 112 | 0 | 115 |
| google-adk | 2.13.0 | 12 / 12 | 25 | +7 | 44 | 90 | 0 | 108 |
| crewai | 1.15.29 | 12 / 12 | 25 | +7 | 51 | 32 | 0 | 111 |
| autogen | 0.7.5 | 12 / 12 | 25 | +7 | 49 | 161 | 0 | 135 |
| langgraph | 1.2.17 | 12 / 12 | 18 | +0 | 37 | 55 | 0 | 81 |
<!-- END:matrix -->

<!-- BEGIN:features -->
| framework | handoff | tracing | human approval | state |
| --- | --- | --- | --- | --- |
| plain-python | function returns next agent | own Trace list | in-tool callback | local variables |
| openai-agents | native `handoffs=[...]` | custom TracingProcessor (SDK spans) | native `needs_approval` + RunState resume | RunState (serialisable) |
| google-adk | native `sub_agents` + transfer_to_agent | Event stream | native `require_confirmation` + resume | InMemorySessionService |
| crewai | native delegation tool | event bus (tool events) | in-tool callback (no per-tool pause) | crew/task context |
| autogen | native Swarm handoffs | run_stream messages/events | Swarm handoff to user + resume | team message thread |
| langgraph | conditional edge | stream_mode=updates | native `interrupt()` + Command(resume) | checkpointer (MemorySaver) |
<!-- END:features -->

<!-- BEGIN:scenarios -->
| scenario | plain-python | openai-agents | google-adk | crewai | autogen | langgraph |
| --- | --- | --- | --- | --- | --- | --- |
| S01 status | pass (1 tools) | pass (1 tools) | pass (1 tools) | pass (1 tools) | pass (1 tools) | pass (1 tools) |
| S02 unknown order | pass (1 tools) | pass (1 tools) | pass (1 tools) | pass (1 tools) | pass (1 tools) | pass (1 tools) |
| S03 no order id | pass (0 tools) | pass (0 tools) | pass (0 tools) | pass (0 tools) | pass (0 tools) | pass (0 tools) |
| S04 refund approved | pass (2 tools) | pass (2 tools) | pass (3 tools) | pass (3 tools) | pass (3 tools) | pass (2 tools) |
| S05 refund denied | pass (2 tools) | pass (2 tools) | pass (3 tools) | pass (3 tools) | pass (3 tools) | pass (2 tools) |
| S06 full refund | pass (2 tools) | pass (2 tools) | pass (3 tools) | pass (3 tools) | pass (3 tools) | pass (2 tools) |
| S07 over policy limit | pass (2 tools) | pass (2 tools) | pass (3 tools) | pass (3 tools) | pass (3 tools) | pass (2 tools) |
| S08 over order total | pass (2 tools) | pass (2 tools) | pass (3 tools) | pass (3 tools) | pass (3 tools) | pass (2 tools) |
| S09 injected notes, status | pass (1 tools) | pass (1 tools) | pass (1 tools) | pass (1 tools) | pass (1 tools) | pass (1 tools) |
| S10 injected notes, refund | pass (2 tools) | pass (2 tools) | pass (3 tools) | pass (3 tools) | pass (3 tools) | pass (2 tools) |
| S11 approver deny by default | pass (2 tools) | pass (2 tools) | pass (3 tools) | pass (3 tools) | pass (3 tools) | pass (2 tools) |
| S12 PII in message | pass (1 tools) | pass (1 tools) | pass (1 tools) | pass (1 tools) | pass (1 tools) | pass (1 tools) |
<!-- END:scenarios -->

Tests at last render: <!-- BEGIN:tests -->83<!-- END:tests -->.

## Reading the numbers

- **Scenarios passed** is the headline. A pass needs all seven checks.
- **Extra vs plain** comes from context across a handoff. In ADK, triage's tool result reaches billing as quoted
  transcript text ("For context: ... [triage] tool returned result"). CrewAI delegation and AutoGen tool-call summaries
  also arrive as text, and the policy only uses structured tool results, so billing looks the order up again.
- **Framework trace spans** shows how much each framework emits by default, not how useful it is.

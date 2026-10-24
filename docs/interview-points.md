# Interview points

- **Same agent, same model, six frameworks:** every adapter passes 12/12 offline with 0 network attempts, so the comparison is about wiring.
- **Context across handoffs differs:** ADK, CrewAI and AutoGen each needed 7 extra lookups, because billing got triage's result as text rather than a structured tool result. The OpenAI Agents SDK and LangGraph did not.
- **Native human approval:** the OpenAI Agents SDK (`needs_approval` plus RunState), ADK (`require_confirmation`), LangGraph (`interrupt`) and an AutoGen Swarm handoff to the user can all pause and resume. CrewAI needed an in-tool callback.
- **The eval was tested too:** a mutant agent that follows injected notes showed the check would crash on a refund with no approval span. That was fixed into a proper failure.
- **Claims are tested:** every feature-matrix cell has a code marker test.

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

Tests: <!-- BEGIN:tests -->83<!-- END:tests -->.

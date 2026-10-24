# Limitations

- **Scripted model.** Results show wiring and control flow, not how well each framework steers a real LLM, recovers from bad tool calls, or handles streaming.
- **Narrow slice of each framework.** No memory services, built-in guardrails, evaluators, deployment or UI tooling.
- **CrewAI approval** is an in-tool callback, because Task `human_input` reviews final output on stdin and does not pause a single tool call.
- **The AutoGen approval** encodes the decision as a user message (APPROVED or DENIED) that our client interprets. That is the Swarm pattern, but the convention is ours.
- **Network blocker** patches Python sockets and DNS only.
- **Extra tool calls** depend on this policy trusting only structured tool results. A policy that parsed transcript text would avoid them, at the cost of treating text from another agent as data.
- **Versions move fast.** Results hold for the pinned versions only.
- **12 scenarios** make a regression suite, not a benchmark.

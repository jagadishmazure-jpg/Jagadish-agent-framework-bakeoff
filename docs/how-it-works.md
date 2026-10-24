# How it works, step by step

1. The runner starts `.envs/<framework>/bin/python -m bakeoff.eval <framework>`.
2. For each scenario, the eval opens `no_network()`, calls `adapter.run(text, approver)` and gets an `Outcome`: final reply, agents visited, tool calls, approvals asked, ledger and trace.
3. Inside the adapter, the framework calls our model class whenever it needs a model turn. The model class turns the
   framework's message format back into (agent, user text, structured tool results), calls `policy.decide`, and
   returns the framework's own response type: a tool call, a handoff call or text.
4. Handoffs use the framework's mechanism: SDK `handoffs`, ADK `transfer_to_agent`, CrewAI's delegation tool, an AutoGen Swarm `transfer_to_billing`, a LangGraph conditional edge.
5. Approval:
   - **OpenAI Agents SDK:** the run stops with `interruptions`, and we call `state.approve` or `state.reject`, then resume.
   - **ADK:** an `adk_request_confirmation` call comes back, and we answer `{"confirmed": bool}`.
   - **AutoGen:** billing hands off to `user`, and we resume with a user `HandoffMessage`.
   - **LangGraph:** `interrupt()` pauses, and `Command(resume=bool)` continues.
   - **CrewAI and plain Python:** the tool calls the approver before any side effect.
6. Tracing: the adapter records our own spans (input, model, tool, approval, handoff, final), all PII-masked, plus the framework's own spans or events with a `framework:` prefix.
7. `check()` compares the outcome with the scenario's expectations, and the results go back as JSON.

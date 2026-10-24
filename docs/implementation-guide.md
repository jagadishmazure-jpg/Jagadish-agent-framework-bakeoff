# Implementation guide

1. **Write the spec once, as code.** Keep tools, approval rules and limits framework-free (`domain.py`). Adapters only wire them.
2. **Put the money check in the tool, not just the framework.** Native pauses are great UX, but the tool should still refuse without approval.
3. **Drive every framework with the same model interface first.** A deterministic stand-in shows wiring bugs before LLM noise hides them. Then swap in a real model behind the same class.
4. **Grade with mutants.** Check that the suite fails an agent that skips approval, obeys injected text, or leaks PII.
5. **Measure context loss across handoffs.** Count repeated tool calls after a handoff; it shows what the framework actually passes along.
6. **Back each matrix claim with a test** that the named API is in the code.
7. **Isolate dependency trees** with one env per framework, plus lock files.

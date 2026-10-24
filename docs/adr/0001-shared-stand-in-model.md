# ADR 0001: One deterministic stand-in model shared by every adapter

**Status:** accepted

**Context.** Real LLMs cost money, need keys and add run-to-run noise that would hide framework differences.

**Decision.** `policy.decide` is the model. Each adapter implements its framework's model interface around it.

**Consequences.** Free, reproducible CI, with differences that come from the frameworks. Nothing here measures LLM steering quality.

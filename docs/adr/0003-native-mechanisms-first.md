# ADR 0003: Use each framework's native mechanism, and say when there is none

**Status:** accepted

**Context.** A bake-off is only fair if each framework is used the way it is meant to be used.

**Decision.** Use native handoffs, approval pauses and tracing hooks wherever they exist. Where they don't (CrewAI per-tool approval), use the simplest honest substitute and label it in the matrix.

**Consequences.** The adapters are longer than a lowest-common-denominator version, and the matrix is backed by code-marker tests.

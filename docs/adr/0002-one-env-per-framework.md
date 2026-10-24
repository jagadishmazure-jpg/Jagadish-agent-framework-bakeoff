# ADR 0002: One pinned virtualenv per framework

**Status:** accepted

**Context.** Installing all five frameworks into one env sent pip's resolver into long backtracking, which we observed while building this.

**Decision.** `.envs/<name>` per framework, built from `requirements/<name>.txt`. The runner calls each adapter in a subprocess.

**Consequences.** Reproducible, conflict-free installs. CI takes a few minutes longer, and the base env needs no framework at all.

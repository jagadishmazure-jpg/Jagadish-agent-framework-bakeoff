# Purpose and audience

Framework comparisons usually set one framework's polished demo against another's quickstart. This repo builds **one**
agent with a fixed spec (two tools, one handoff, one human approval, tracing) in plain Python and five frameworks.
It drives all six with the same deterministic stand-in model and grades them with the same suite, so the remaining
differences come from the frameworks.

| reader | start here |
| --- | --- |
| Choosing a framework | README matrix and feature table |
| Reviewing rigour | `src/bakeoff/eval.py`, `tests/test_eval_suite.py` (mutants), `tests/test_matrix_claims.py` |
| Porting the pattern | `docs/implementation-guide.md` |

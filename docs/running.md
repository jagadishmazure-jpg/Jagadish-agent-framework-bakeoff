# Running

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
scripts/make_envs.sh
ruff check . && ruff format --check .
pytest -q
python scripts/count_tests.py
bakeoff demo
python scripts/render_docs.py --check
python scripts/check_brands.py
```

Pinned framework versions (full lock files in `requirements/`): openai-agents 0.24.0, google-adk 2.13.0,
crewai 1.15.29, autogen-agentchat 0.7.5 and autogen-core 0.7.5, langgraph 1.2.17. Tooling: pytest 8.4.2, ruff 0.14.1, Python 3.13.

To run a single framework: `.envs/langgraph/bin/python -m bakeoff.eval langgraph`.

To refresh a lock file after a deliberate upgrade: rebuild the env, then `pip freeze --exclude-editable > requirements/<name>.txt`, and update the pyproject extra.

**Optional real models:** not written. The planned path is an OpenAI-compatible local server behind each framework's normal client, run by hand and skipped in CI.

**Originality:** `python scripts/overlap_check.py <reference.txt>` reports 8-word overlaps.

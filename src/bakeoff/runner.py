"""Run the eval suite for every adapter, each in its own pinned virtualenv, and collect the results.

Frameworks live in separate envs under `.envs/<name>` (built by scripts/make_envs.sh from requirements/),
because their dependency trees do not resolve together quickly. Plain Python runs in the current env.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

from .eval import ADAPTERS

ROOT = Path(__file__).resolve().parents[2]
ENVS = ROOT / ".envs"


def python_for(name: str) -> Path | None:
    if name == "plain-python":
        return Path(sys.executable)
    p = ENVS / name / "bin" / "python"
    return p if p.exists() else None


def run_one(name: str) -> dict:
    py = python_for(name)
    if py is None:
        return {"adapter": name, "available": False, "reason": f"no env at .envs/{name}"}
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    r = subprocess.run([str(py), "-m", "bakeoff.eval", name], capture_output=True, text=True, timeout=600, env=env, cwd=ROOT)
    if r.returncode != 0:
        return {"adapter": name, "available": False, "reason": r.stderr.strip().splitlines()[-1:] or ["error"]}
    return json.loads(r.stdout.strip().splitlines()[-1])


def run_all() -> list[dict]:
    return [run_one(n) for n in ADAPTERS]


def code_lines(path: Path) -> int:
    """Lines of code: no blanks, comments or docstrings."""
    src = path.read_text()
    tree = ast.parse(src)
    doc = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and ast.get_docstring(node):
            d = node.body[0]
            doc.update(range(d.lineno, d.end_lineno + 1))
    return sum(
        1 for i, line in enumerate(src.splitlines(), 1) if line.strip() and not line.strip().startswith("#") and i not in doc
    )


def adapter_loc(name: str) -> int:
    mod = ADAPTERS[name].rsplit(".", 1)[1]
    return code_lines(ROOT / "src" / "bakeoff" / "adapters" / f"{mod}.py")

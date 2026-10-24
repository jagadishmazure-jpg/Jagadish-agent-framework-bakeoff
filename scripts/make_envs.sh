#!/usr/bin/env bash
# Build one virtualenv per framework under .envs/, from the pinned lock files in requirements/.
# Frameworks get separate envs because their dependency trees do not resolve together quickly.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-python3}
for name in openai-agents google-adk crewai autogen langgraph; do
  if [ ! -x ".envs/$name/bin/python" ]; then
    "$PY" -m venv ".envs/$name"
  fi
  ".envs/$name/bin/python" -m pip install -q -r "requirements/$name.txt"
  ".envs/$name/bin/python" -m pip install -q -e . --no-deps
  echo "env ready: $name"
done

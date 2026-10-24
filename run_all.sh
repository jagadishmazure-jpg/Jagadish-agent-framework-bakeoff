#!/bin/sh
cd /workspace/bake
for e in .venv .env-*; do $e/bin/pip -q install -e . --no-deps >/dev/null 2>&1; done
for f in plain-python:.venv openai-agents:.env-openai-agents google-adk:.env-google-adk crewai:.env-crewai autogen:.env-autogen-agentchat langgraph:.env-langgraph; do
  n=${f%%:*}; e=${f#*:}
  timeout 300 $e/bin/python -m bakeoff.eval $n > /tmp/ev-$n.json 2>/tmp/ev-$n.err
  python3 -c "
import json; d=json.load(open('/tmp/ev-$n.json')); r=d['rows']
print(d['adapter'], d.get('version'), sum(x['ok'] for x in r), '/', len(r), d['total_ms'],'ms')
[print('   ',x['id'],x['errors']) for x in r if not x['ok']]" || tail -3 /tmp/ev-$n.err
done
echo ALLDONE

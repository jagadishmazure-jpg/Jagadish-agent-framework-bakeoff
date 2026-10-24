# Threat model

## STRIDE

| threat | example | mitigation | residual |
| --- | --- | --- | --- |
| Spoofing | order notes posing as a system message | marked untrusted; policy ignores tool-output instructions | a real LLM can still be persuaded; the tool-level approval and caps limit the damage |
| Tampering | model inflates the refund amount | amount from customer text; tool caps | a customer can ask for any amount up to the caps, and a human still approves |
| Repudiation | who approved what? | approval span with order id, amount and decision | traces are in memory only |
| Information disclosure | PII in traces; telemetry upload | masking; network blocker; telemetry off | Python-level blocker only |
| Denial of service | handoff loop | max turns or recursion limit in every adapter | - |
| Elevation of privilege | triage issuing refunds | only billing has `issue_refund` (except plain/CrewAI internals, which still require approval) | - |

## OWASP Top 10 for LLM applications

| item | control |
| --- | --- |
| LLM01 Prompt injection | untrusted tool output; S09 and S10 |
| LLM02 Sensitive information disclosure | trace masking; S12 |
| LLM03 Supply chain | pinned lock files, Dependabot, CodeQL |
| LLM06 Excessive agency | approval gate, tool caps, tools scoped per agent |
| LLM10 Unbounded consumption | turn limits |

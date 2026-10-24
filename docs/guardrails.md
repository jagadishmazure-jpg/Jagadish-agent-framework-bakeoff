# Guardrails

| risk | control | evidence |
| --- | --- | --- |
| Money moves without consent | approval before `issue_refund` in every adapter; the tool refuses unapproved calls; approver denies by default | S05, S11; mutant `test_catches_refund_without_approval` |
| Approval asked after the fact | eval checks that the approval span comes before the refund span | `check()` |
| Over-refund | tool caps at the order total and the 200.00 policy limit | S07, S08 |
| Injection through tool output | notes returned as `untrusted_notes`; policy never takes actions or amounts from tool output | S09, S10; mutant test |
| PII in traces | every span value masked | S12; mutant `test_catches_unmasked_trace` |
| Silent telemetry or network | socket and DNS blocker counts attempts; CrewAI telemetry disabled by env | `net attempts` column = 0 |
| Matrix overclaims | API markers checked in adapter source | `test_matrix_claims.py` |
| Version drift | lock files plus test comparing runtime version to pins | `test_pinned_version_matches_requirements` |

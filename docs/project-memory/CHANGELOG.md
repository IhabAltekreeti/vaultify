# Vaultify — Changelog

## 2026-08-23 — Persistent project memory introduced
- Added `docs/project-memory/`.
- Added `format/` for memory, AI handoff, and communication rules.
- Recorded R1 closure and proven architecture.
- Recorded Groq migration context.
- Recorded isolated PASS evidence for `openai/gpt-oss-120b` and `openai/gpt-oss-20b`.
- Kept full canonical regression as the migration acceptance gate.
- Established GPT / USER / Spark operating roles.

## Historical baseline
- Phase 3.8: CLOSED.
- R1 Release Extraction: CLOSED at Step 29.
- Final extracted regression gate: `33 passed in 4.53s`.
- Real Claude → OAuth → MCP → `ask_documents`: PASS.

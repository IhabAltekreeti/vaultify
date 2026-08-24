# Vaultify — Changelog

## 2026-08-24 — GPT ↔ Spark memory protocol hardened
- Added mandatory nine-section Spark operation reporting format.
- Added Spark execution guardrails and stop conditions.
- Added GPT → Spark bounded handoff template.
- Updated `HANDOFF_GPT_SPARK.md` to make the reporting and approval protocol mandatory.
- Added explicit evidence-vs-assumption rules.
- Added explicit fallback/LLM execution-path reporting requirements.
- Added scope-control, Git safety, secret-handling, and test-integrity rules.
- Added migration gate: discover → isolated test → evidence → GPT review → source change → regression.

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

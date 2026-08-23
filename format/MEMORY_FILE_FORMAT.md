# Memory File Format

## Purpose
Persistent project memory for Vaultify. It allows a new AI session to recover project state without reconstructing months of chat history.

## Rules
1. Write memory files in English.
2. Prefer facts and decisions over narrative.
3. Separate proven evidence from assumptions.
4. Include dates when state may change.
5. Never store secrets, API keys, tokens, passwords, OAuth codes, or private credentials.
6. Do not silently rewrite history when new evidence conflicts with older memory. Record corrections in `CHANGELOG.md` or `DECISIONS.md`.
7. Keep `CURRENT_STATE.md` concise enough for session startup.
8. Keep `TODO.md` actionable and prioritized.
9. Keep `REGRESSION.md` evidence-oriented.
10. Keep `HANDOFF_GPT_SPARK.md` operational.

## File responsibilities
- `CURRENT_STATE.md`: what is true now.
- `DECISIONS.md`: decisions that should not be re-litigated without evidence.
- `TODO.md`: prioritized next work.
- `REGRESSION.md`: verified tests and acceptance evidence.
- `HANDOFF_GPT_SPARK.md`: AI roles and transfer protocol.
- `CHANGELOG.md`: dated changes.

## Update rule
At the end of a meaningful implementation unit, update the smallest relevant memory files and commit them with the related work.

## Source-of-truth rule
Code truth comes from GitHub source. Memory explains state; it does not replace code or tests.

# Vaultify — TODO

## 🔴 Current priority — Groq migration acceptance
1. Run full canonical regression against the selected Groq model.
2. Verify Apple: `$416,161 million`.
3. Verify Tesla: `$24,901 million`.
4. Verify ambiguity handling.
5. Verify outside-corpus / no-answer behavior.
6. Verify MCP `ask_documents`.
7. Distinguish LLM-generated results from deterministic fallback where possible.
8. Record evidence in `REGRESSION.md`.

## 🟠 R1 / All-In-One finalization
- Keep R1 extraction closed.
- Preserve the completed migration/control notebook as evidence.
- Move toward the clean short V0.1 control notebook that imports the modular repository.
- Keep All-In-One as a snapshot, not source of truth.

## 🔴 R2 — persistence
- PostgreSQL
- Alembic migrations
- persistent OAuth state
- object storage

## 🟠 R3 — deployment
- stable HTTPS
- deployment configuration
- CPU/RAM benchmark
- review CUDA dependencies for production

## 🟡 R4 — minimal UX
- branded OAuth
- dashboard
- documents
- upload
- Ask Vaultify
- connector management

## 🟠 R5 — security / deployed regression
- deployed regression suite
- tenant isolation
- IDOR
- authentication
- data leakage
- MCP
- OAuth

## 🟢 V1
- final V1 acceptance

## Current migration non-goals
Do not simultaneously change Qdrant, embeddings, retrieval, MCP, OAuth, or tenant isolation.

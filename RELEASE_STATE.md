# Vaultify Release State

## Current release track
- Target: Vaultify V0.1 Technical Preview
- Active branch: `release/v0.1-extraction`
- Golden baseline commit: `8b1c3e7005611aaae66250b01edd139a05801d0e`
- Phase 3.8 historical milestone: CLOSED
- Phase 3.8 extracted release-parity acceptance: CLOSED
- R1 Release Extraction: CLOSED (100% COMPLETE)
- All-In-One Notebook Status: Cells 0–13 VERIFIED (33/33 tests PASS)
- Active LLM Model: `openai/gpt-oss-120b` (Groq model migration verified)
- Next Active Stage: `R2 — Production Persistence (PostgreSQL, Object Storage & Persistent OAuth)`

## Source-of-truth rule
1. Golden notebook saved code + outputs (Immutable historical baseline)
2. Matching exported Python file
3. Release extraction plan / state documents
4. Extracted `src/vaultify/` implementation (Current application truth)

## Completed Milestones
- [x] Model Compatibility: Migrated from decommissioned `llama-3.3-70b-versatile` to `openai/gpt-oss-120b`.
- [x] R0 Golden Reference: Phase 3.8 sealed.
- [x] R1 Release Extraction: 30 product modules, 17 regression test modules, 2 control scripts extracted.
- [x] All-In-One Notebook Assembly:
  - Cell 0: Runtime dependencies (`flask`, `flask-login`, `flask-sqlalchemy`, `flask-wtf`, `filetype`, `groq`, `qdrant-client`, `sentence-transformers`, `mcp<2`, `pydantic`, `starlette`, `httpx`).
  - Cell 1: Snapshot contract.
  - Cell 2: Source sync & professional boundary verification.
  - Cell 3: Clean architecture map.
  - Cell 4: Module dependency map (19 levels).
  - Cell 5: External dependency classification.
  - Cell 6: Secrets & config boundary audit (PASS with `openai/gpt-oss-120b`).
  - Cell 7: Core configuration, extensions & database models (PASS).
  - Cell 8: Embeddings (MiniLM 384d), Qdrant Cloud & Groq client (PASS).
  - Cell 9: Canonical Chunker V2 (240 token ceiling, table awareness), PDF validation, document catalog (PASS).
  - Cell 10: Hybrid retrieval, entity routing, evidence verification & grounded answer (5 golden behaviors PASS).
  - Cell 11: Flask web app, login/logout, multi-tenancy isolation & /ask flow (PASS).
  - Cell 12: Connector credentials lifecycle, SHA-256 hash storage, MCP/OAuth boundaries (PASS).
  - Cell 13: Final full regression test suite (17 modules, 33 tests passed in 4.53s).

## Core Verified Evidence
- Apple FY2025 total net sales: `$416,161 million` (`apple_fy2025_10k.pdf`, `Note 2 - Revenue`).
- Tesla Q4 2025 total revenue: `$24,901 million` (`tesla_q4_2025_update.pdf`).
- Comparison preserves dual sources with reporting period mismatch warning.
- Ambiguous queries require clarification before LLM generation.
- Outside-corpus queries return no-answer without LLM generation.
- Client-controlled `tenant_id` and `organization_id` overrides rejected.
- Zero cross-tenant data leakage.

## Next Release Stages
- R2 — Production Persistence: PostgreSQL database, Alembic/Flask-Migrate migrations, persistent object storage for PDFs, persistent OAuth state.
- R3 — Stable Deployment: Stable HTTPS host, CPU/RAM benchmarks, removal of mandatory CUDA assumptions.
- R4 — Minimal V1 UX: Branded authorization UI, dashboard improvements.
- R5 — Phase 3.10 Security & Deployed Regression Gate (V0.1 Technical Preview acceptance).

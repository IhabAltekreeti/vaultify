# Vaultify Release State

## Current release track
- Target: Vaultify V0.1 Technical Preview
- Active branch: `release/v0.1-extraction`
- Golden baseline commit: `53eb736646ecf88c8551a490606014ed5307b6ae`
- Phase 3.8: CLOSED
- R1 Release Extraction: IN PROGRESS
- Remote reconciliation checkpoint: CLEAN / CONSISTENT THROUGH R1 STEP 15

## Source-of-truth rule
1. Golden notebook saved code + outputs
2. Matching exported Python file
3. Release extraction plan / state documents
4. Extracted `src/vaultify/` implementation

The golden notebook remains immutable. The Python export is derived and may contain Colab-export mutations; the notebook wins on conflicts.

## R1 completed steps
- Step 1 — stable non-secret config: PASS
- Step 2 — shared Flask extensions: PASS
- Step 3 — core web models: PASS
- Step 4 — trusted membership / tenant resolution: PASS
- Step 5 — minimal Flask auth + `/ask`: PASS
- Security Gate 1 — Flask request-flow / tenant isolation: PASS (`1 passed`)
- Step 6 — embedding service: PASS
- Embedding normalization parity gate: PASS
- Step 7 — Qdrant runtime + Colab secret adapter: PASS
- Step 8 — Groq runtime + Colab secret adapter: PASS
- Step 9 — tenant-scoped Qdrant corpus loading: PASS
- Step 10 — Dense + BM25 + RRF critical hybrid regression: PASS
- Step 11 — deterministic Query Analyzer V1: PASS
- Step 12 — tenant document catalog + entity registry: PASS
- Step 13 — entity-routed hybrid retrieval: PASS
- Step 14 — structured evidence verification: PASS
- Step 15 — grounded answer generation + clean `answer_question_v2`: PASS

## Validation evidence
### Flask security gate
- Real `Flask.test_client()` path covered.
- Unauthenticated `/ask` redirects to login; valid login and logout work.
- Empty questions are rejected before answer-service invocation.
- Answered, clarification, and no-answer outputs render through the real route.
- `QueryLog` persists accepted questions against authenticated user/org.
- Browser-controlled `tenant_id` / unauthorized `organization_id` cannot override authenticated membership tenant.

### Embeddings / cloud clients
- Embedding model: `sentence-transformers/all-MiniLM-L6-v2`; vector dimension 384; document/query embeddings unit-normalized.
- Qdrant Cloud connection PASS; `vaultify_v3_documents` found; factory timeout 60 seconds.
- Groq connection PASS; model `llama-3.3-70b-versatile`; no secret value is stored in application source.
- Steps 7–15 created, updated, or deleted no Qdrant points.

### Hybrid retrieval
- Golden Cell 19B core preserved: normalized dense embeddings; BM25 `k1=1.5`, `b=0.75`; one-based ranks; RRF constant `60`; lexical coverage, phrase, year, and quantitative-table bonuses.
- Live regression PASS: Apple canonical chunks 609; Tesla canonical chunks 140; Apple `416,161` and Tesla `24,901` evidence reached top-6.

### Query Analyzer / catalog / routing
- Cell 21A-style catalog, Cell 21B analyzer, Cell 21C routing, and active Cell 21C.1 aggregate-metric patch are extracted.
- Runtime catalog/analyzer/routing are dependency-driven; Apple/Tesla remain regression fixtures rather than hardcoded tenants.
- Catalog fails closed on cross-tenant chunk input.
- Mixed tenant routes Apple/Tesla independently; strict Tesla tenant rejected Apple retrieval.
- Ambiguous and outside-corpus questions stop before retrieval.

### Structured evidence verification
- Golden Cell 21D behavior extracted into `services/evidence_verification.py`.
- Evidence is verified only when metric + reporting period + numeric value are jointly supported.
- Table evidence prefers metric-row / requested-period-column extraction; text-window extraction is fallback.
- Live Step 14 PASS: Apple `416,161`, Tesla `24,901`, and comparison all verified.
- First comparison exposed missing Cell 21C.1 `net_sales -> total net sales + net sales`; parity was restored before PASS.

### Grounded answer generation
- Golden Cell 21E behavior extracted into `services/grounded_answer.py`.
- `answer_question_v2` now uses explicit tenant/runtime/index/client dependencies instead of notebook globals.
- Live Step 15 PASS with real Groq: Apple, Tesla, and comparison answers preserved verified values.
- Clarification and outside-corpus no-answer gates do not call Groq.
- Invalid/incomplete model answers fall back to deterministic verified answers in committed pytest.
- Runtime tenant mismatch fails closed before retrieval.
- Cell 21E.1 unit-context patch is intentionally still pending; Step 15 does not claim final million-dollar formatting parity.

## Flask evidence-gap status
The missing canonical Cell 22D / stale `FLASK_REQUEST_FLOW_REGRESSION_PASSED` evidence gap is CLOSED for extracted code by `tests/regression/test_flask_request_flow.py`.

This does not yet prove the clean V2 orchestrator is wired into the real Flask route; that remains a later integration gate.

## Extracted runtime surface
- `src/vaultify/config.py`
- `src/vaultify/extensions.py`
- `src/vaultify/models/__init__.py`
- `src/vaultify/web/__init__.py`
- `src/vaultify/web/tenancy.py`
- `src/vaultify/web/app.py`
- `src/vaultify/templates/login.html`
- `src/vaultify/templates/dashboard.html`
- `src/vaultify/services/embeddings.py`
- `src/vaultify/services/qdrant.py`
- `src/vaultify/services/llm.py`
- `src/vaultify/services/retrieval.py`
- `src/vaultify/services/query_analyzer.py`
- `src/vaultify/services/document_catalog.py`
- `src/vaultify/services/entity_routing.py`
- `src/vaultify/services/evidence_verification.py`
- `src/vaultify/services/grounded_answer.py`
- `tests/regression/` for extracted deterministic gates
- `notebooks/Vaultify_R1_Control_Panel.ipynb`

## Test-evidence boundary
- Committed pytest covers deterministic/security behavior; live Qdrant/model gates use explicit Colab regression evidence.
- Module reload is required in a long-lived Colab runtime after `git pull` when already-imported modules changed.

## Intentionally not extracted yet
- Cell 21E.1 context-aware financial unit resolution
- clean V2 Flask web adapter / real Flask V2 integration
- ingestion / Docling / OCR
- upload and full document-management routes
- ConnectorCredential release model
- OAuth
- MCP
- Cloudflare / tunnel runtime
- production persistence / migrations
- stable deployment configuration
- Phase 3.9 product work

## Guardrails
- GitHub is source/control infrastructure, not the project goal.
- Main goal: turn the golden notebook/export into a clean, modular, readable Vaultify codebase.
- Split by responsibility, not arbitrary line count.
- Do not redesign working retrieval, OAuth, MCP, or security behavior during extraction.
- Do not start Phase 3.9 or drift into persistence/deployment while cleaning the monolith.
- Continue only as: one logical extraction unit → regression → PASS/FAIL → next unit.
- Apple/Tesla remain regression fixtures; runtime services accept dynamic tenant data and registries.
- Keep eventual modular, control-panel, and All-In-One notebook outputs without making the notebook the source of truth.

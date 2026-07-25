# Vaultify Release State

## Current release track
- Target: Vaultify V0.1 Technical Preview
- Active branch: `release/v0.1-extraction`
- Golden baseline commit: `53eb736646ecf88c8551a490606014ed5307b6ae`
- Phase 3.8: CLOSED
- R1 Release Extraction: IN PROGRESS
- Remote reconciliation checkpoint: CLEAN / CONSISTENT THROUGH R1 STEP 13

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

## Validation evidence
### Flask security gate
- Real `Flask.test_client()` path covered.
- Unauthenticated `/ask` redirects to login; valid login and logout work.
- Empty questions are rejected before answer-service invocation.
- Answered, clarification, and no-answer outputs render through the real route.
- `QueryLog` persists accepted questions against authenticated user/org.
- Browser-controlled `tenant_id` / unauthorized `organization_id` cannot override authenticated membership tenant.

### Embeddings
- Model: `sentence-transformers/all-MiniLM-L6-v2`; vector dimension: 384.
- Document and query embeddings verified unit-normalized.
- Extracted service does not hardcode Colab/CUDA; platform device selection stays a runtime concern.

### Qdrant
- Secrets loaded only through the Colab control-panel adapter.
- Qdrant Cloud connection PASS; `vaultify_v3_documents` found.
- Factory timeout reconciled to golden runtime value: 60 seconds.
- Step 9 observed: Apple tenant 745 chunks; Tesla tenant 140 chunks; point sets disjoint.
- Steps 7–13 created, updated, or deleted no Qdrant points.

### Groq
- Secret loaded only through the Colab control-panel adapter.
- Model: `llama-3.3-70b-versatile`.
- Live completion probe returned a non-empty response.
- No secret value is stored in application source.

### Hybrid retrieval
- Golden Cell 19B core algorithm compared against extracted code.
- Preserved: normalized dense embeddings; BM25 `k1=1.5`, `b=0.75`; one-based ranks; RRF constant `60`; lexical coverage, phrase, year, and quantitative-table bonuses.
- Notebook-global embedding access was replaced by explicit `EmbeddingService` dependency injection; ranking formula is unchanged.
- Critical live regression PASS: Apple canonical chunks 609; Tesla canonical chunks 140; Apple `$416,161M` and Tesla `$24,901M` evidence reached top-6; tenant identity stayed intact.
- IMPORTANT: Step 10 reran the two critical canonical questions, not every historical Cell 19B benchmark case.

### Query Analyzer V1
- Golden Cell 21B deterministic analyzer behavior is preserved.
- Entity registry is supplied as a dependency; application code does not hardcode Apple/Tesla tenants.
- Apple single-entity, Tesla single-entity, comparison decomposition, ambiguity clarification, and outside-corpus no-answer candidate regression passed.
- No embedding, Qdrant, or Groq call is required for query planning.

### Tenant document catalog / entity registry
- Golden Cell 21A-style document grouping is extracted into `services/document_catalog.py`.
- Documents group by `document_hash` when available, otherwise by normalized filename.
- Catalog records preserve tenant, filename, hash, chunk counts, chunk types, years, sections, entities, aliases, and normalized chunks.
- Application runtime is generic: entity rules are caller-supplied and unknown customer files use a readable filename-derived fallback.
- Catalog builder fails closed if a supplied chunk belongs to a different tenant.
- Live Step 12 PASS: Apple tenant 745 chunks / 2 documents; Tesla tenant 140 chunks / 1 document; canonical cross-tenant files did not leak.

### Entity-routed hybrid retrieval
- Golden Cell 21C/21C.1 routing behavior is extracted into `services/entity_routing.py`.
- One Dense + BM25 hybrid index is prepared per entity; routes search only the selected entity's registered documents.
- Metric expansions preserve the canonical Apple/Tesla financial regression behavior without hardcoding tenant IDs.
- Mixed-corpus tenant live PASS: Apple and Tesla questions routed independently; comparison produced separate Apple/Tesla routes; `$416,161M` and `$24,901M` evidence reached routed top-6.
- Strict Tesla tenant rejected Apple retrieval.
- Ambiguous and outside-corpus questions stop before retrieval in committed regression.
- The first live Step 13 cell incorrectly treated the historical mixed corpus as Apple-only; corrected semantics distinguish tenant isolation from entity routing.

## Flask evidence-gap status
The missing canonical Cell 22D / stale `FLASK_REQUEST_FLOW_REGRESSION_PASSED` evidence gap is CLOSED for extracted code by `tests/regression/test_flask_request_flow.py`.

This does not prove live Qdrant/Groq/V2 answer orchestration; those remain separate integration concerns.

## Extracted runtime surface
- `src/vaultify/config.py`
- `src/vaultify/extensions.py`
- `src/vaultify/models/__init__.py`
- `src/vaultify/web/__init__.py`
- `src/vaultify/web/tenancy.py`
- `src/vaultify/web/app.py`
- `src/vaultify/templates/login.html`
- `src/vaultify/templates/dashboard.html`
- `src/vaultify/services/__init__.py`
- `src/vaultify/services/embeddings.py`
- `src/vaultify/services/qdrant.py`
- `src/vaultify/services/llm.py`
- `src/vaultify/services/retrieval.py`
- `src/vaultify/services/query_analyzer.py`
- `src/vaultify/services/document_catalog.py`
- `src/vaultify/services/entity_routing.py`
- `tests/regression/test_flask_request_flow.py`
- `tests/regression/test_query_analyzer.py`
- `tests/regression/test_document_catalog.py`
- `tests/regression/test_entity_routing.py`
- `notebooks/Vaultify_R1_Control_Panel.ipynb`

## Test-evidence boundary
- Committed pytest covers Flask request-flow security, Query Analyzer V1, document catalog safety, and entity-routing control flow.
- Steps requiring live Qdrant/model behavior also include explicit Colab regression evidence.
- The Step 10 import failure was Python module caching after `git pull`; module reload resolved it and the actual hybrid regression passed.
- The corrected Step 12/13 live tests use the actual historical tenant layout instead of assuming the mixed corpus is Apple-only.

## Intentionally not extracted yet
- structured evidence verification / evidence selection
- answer orchestration / grounded answer service
- ingestion / Docling / OCR
- upload and full document-management routes
- ConnectorCredential release model
- OAuth
- MCP
- Cloudflare / tunnel runtime
- production persistence / migrations
- stable deployment configuration
- Phase 3.9 product work

## Reconciliation findings
- Branch is a clean forward extraction from the golden baseline; golden files were not modified by R1.
- Current modules are responsibility-based, not notebook-cell copies.
- Qdrant timeout parity and Groq helper wording were reconciled; no product feature was added.
- Apple/Tesla remain regression fixtures; runtime catalog, analyzer, and routing accept dynamic tenant data and registries.

## Guardrails from this checkpoint onward
- GitHub is source/control infrastructure, not the project goal.
- Main goal: turn the golden notebook/export into a clean, modular, readable Vaultify codebase.
- Split by responsibility, not arbitrary line count.
- Do not redesign working retrieval, OAuth, MCP, or security behavior during extraction.
- Do not start Phase 3.9 or drift into persistence/deployment while cleaning the monolith.
- Continue only as: one logical extraction unit → regression → PASS/FAIL → next unit.
- Keep an eventual downloadable/local/Drive backup path in addition to GitHub remote source control.

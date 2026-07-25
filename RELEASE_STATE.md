# Vaultify Release State

## Current release track
- Target: Vaultify V0.1 Technical Preview
- Active branch: `release/v0.1-extraction`
- Golden baseline commit: `53eb736646ecf88c8551a490606014ed5307b6ae`
- Phase 3.8: CLOSED
- R1 Release Extraction: IN PROGRESS
- Remote reconciliation checkpoint: CLEAN / CONSISTENT THROUGH R1 STEP 10
- Extraction is PAUSED here until explicit approval to continue.

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
- Steps 7–10 created, updated, or deleted no Qdrant points.

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
- `tests/regression/test_flask_request_flow.py`
- `notebooks/Vaultify_R1_Control_Panel.ipynb`

## Test-evidence boundary
- Committed pytest currently contains the Flask request-flow security gate.
- Steps 6–10 were validated through explicit Colab regression cells with observed PASS outputs.
- These live checks are recorded release evidence but are not all committed pytest tests yet.
- The Step 10 import failure was Python module caching after `git pull`; module reload resolved it and the actual hybrid regression passed.

## Intentionally not extracted yet
- query analyzer / entity routing
- V2 reranking / evidence selection
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
- Largest extracted application module is `services/retrieval.py` at roughly 455 lines, not a multi-thousand-line block.
- Qdrant timeout parity and Groq helper wording were reconciled; no product feature was added.

## Guardrails from this checkpoint onward
- GitHub is source/control infrastructure, not the project goal.
- Main goal: turn the ~36–37k-line golden notebook/Python export into a clean, modular, readable Vaultify codebase.
- Split by responsibility, not arbitrary line count; prefer a few hundred readable lines where natural.
- Do not redesign working retrieval, OAuth, MCP, or security behavior during extraction.
- Do not start Phase 3.9 or drift into persistence/deployment while cleaning the monolith.
- Continue only as: one logical extraction unit → regression → PASS/FAIL → next unit.
- Keep an eventual downloadable/local/Drive backup path in addition to GitHub remote source control.

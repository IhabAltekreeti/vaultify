# Vaultify Release State

## Current release track

- Target: Vaultify V0.1 Technical Preview
- Active branch: `release/v0.1-extraction`
- Golden baseline commit: `53eb736646ecf88c8551a490606014ed5307b6ae`
- Phase 3.8: CLOSED
- R1 Release Extraction: IN PROGRESS
- Remote reconciliation checkpoint: CLEAN / CONSISTENT THROUGH R1 STEP 10
- Extraction is intentionally PAUSED here until explicit approval to continue.

## Source-of-truth rule

1. Golden notebook saved code + outputs
2. Matching exported Python file
3. Release extraction plan / state documents
4. Extracted `src/vaultify/` implementation

The golden notebook remains immutable. The exported Python file is derived and may contain Colab-export mutations; the notebook wins on conflicts.

## R1 completed steps

- R1 Step 1 — stable non-secret config extraction: PASS
- R1 Step 2 — shared Flask extensions extraction: PASS
- R1 Step 3 — core web models extraction: PASS
- R1 Step 4 — trusted membership / tenant resolution: PASS
- R1 Step 5 — minimal Flask auth + `/ask` slice: PASS
- R1 Security Gate 1 — Flask request-flow / tenant isolation: PASS (`1 passed`)
- R1 Step 6 — embedding service extraction: PASS
- Embedding normalization parity gate: PASS
- R1 Step 7 — Qdrant runtime + Colab secret adapter: PASS
- R1 Step 8 — Groq runtime + Colab secret adapter: PASS
- R1 Step 9 — tenant-scoped Qdrant corpus loading: PASS
- R1 Step 10 — Dense + BM25 + RRF hybrid retrieval critical regression: PASS

## Observed live validation evidence

### Flask security gate

- Real `Flask.test_client()` path covered.
- Unauthenticated `/ask` redirects to login.
- Valid login works.
- Empty questions are rejected before answer-service invocation.
- Answered, clarification, and no-answer outputs render through the real Flask route.
- `QueryLog` persists accepted questions against the authenticated user and organization.
- Logout clears authentication.
- Browser-controlled `tenant_id` and unauthorized `organization_id` cannot override the tenant derived from authenticated organization membership.

### Embeddings

- Model: `sentence-transformers/all-MiniLM-L6-v2`
- Vector dimension: 384
- Document and query embeddings verified unit-normalized.
- The extracted service does not hardcode Colab/CUDA; platform device selection remains a runtime concern.

### Qdrant

- `QDRANT_URL` and `QDRANT_API_KEY` loaded through the Colab-only control-panel adapter.
- Qdrant Cloud connection passed.
- Collection `vaultify_v3_documents` found.
- Factory default timeout reconciled to golden runtime value: 60 seconds.
- Step 9 observed tenant corpus counts: Apple tenant 745 chunks, Tesla tenant 140 chunks.
- Apple and Tesla point sets were verified disjoint.
- No Qdrant points were created, updated, or deleted by Steps 7–10.

### Groq

- `GROQ_API_KEY` loaded through the Colab-only control-panel adapter.
- Configured model: `llama-3.3-70b-versatile`.
- Live completion probe returned a non-empty response.
- No secret value is stored in application source code.

### Hybrid retrieval

- Golden Cell 19B core algorithm was compared against extracted code.
- Preserved behavior includes:
  - normalized dense embeddings,
  - BM25 with `k1=1.5`, `b=0.75`,
  - one-based dense and lexical ranks,
  - Reciprocal Rank Fusion with default constant `60`,
  - lexical coverage bonus,
  - phrase bonus,
  - year bonus,
  - quantitative table bonus.
- Extraction replaces notebook-global embedding access with explicit `EmbeddingService` dependency injection; the ranking formula is unchanged.
- Critical live regression passed on canonical documents:
  - Apple canonical chunks indexed: 609
  - Tesla canonical chunks indexed: 140
  - Apple FY2025 `$416,161M` evidence reached top-6
  - Tesla Q4 2025 `$24,901M` evidence reached top-6
  - tenant identity remained intact
- IMPORTANT: this Step 10 live regression covers the two critical canonical questions. It is not evidence that every historical Cell 19B benchmark case has been rerun on the extracted code.

## Flask evidence-gap status

The earlier missing canonical Cell 22D / stale `FLASK_REQUEST_FLOW_REGRESSION_PASSED` evidence gap is CLOSED for the extracted codebase by `tests/regression/test_flask_request_flow.py`.

This does not itself prove live Qdrant/Groq/V2 answer orchestration; those are separate integration concerns.

## Extracted runtime surface so far

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

- The committed pytest regression suite currently contains the Flask request-flow security gate.
- Steps 6–10 were validated through explicit Colab regression cells and observed PASS outputs.
- Their live checks are recorded as release evidence, but they have not yet all been converted into committed pytest tests.
- The Step 10 import failure was caused by Python module caching after `git pull`; module reload resolved it and the actual hybrid regression then passed.

## Intentionally not extracted yet

- query analyzer / entity routing
- V2 reranking and evidence-selection layer
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

- Branch is a clean forward extraction from the golden baseline; no golden files were modified by R1 work.
- Current extracted modules are responsibility-based rather than notebook-cell copies.
- Current largest extracted application module is the hybrid retrieval service at roughly a few hundred lines, not a multi-thousand-line notebook block.
- Qdrant timeout parity was corrected during reconciliation.
- Groq helper wording was corrected so it no longer claims an exact historical probe implementation.
- No new product feature was added during reconciliation.

## Guardrails from this checkpoint onward

- GitHub is a source/control mechanism, not the project goal.
- The main goal is to turn the ~36–37k-line golden notebook/Python export into a clean, modular, readable Vaultify codebase.
- Split by responsibility, not arbitrary line count.
- Prefer readable modules of a few hundred lines where the responsibility naturally allows it.
- Do not redesign working retrieval, OAuth, MCP, or security behavior during extraction.
- Do not start Phase 3.9.
- Do not move into persistence/deployment work while cleaning the monolith.
- Continue only as: one logical extraction unit → regression → PASS/FAIL → next unit.
- Keep an eventual downloadable/local/Drive backup path in addition to GitHub remote source control.

# Vaultify Release State

## Current release track
- Target: Vaultify V0.1 Technical Preview
- Active branch: `release/v0.1-extraction`
- Golden baseline commit: `53eb736646ecf88c8551a490606014ed5307b6ae`
- Phase 3.8 historical milestone: CLOSED
- R1 Release Extraction: IN PROGRESS
- Remote reconciliation checkpoint: CLEAN / CONSISTENT THROUGH R1 STEP 19

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
- Security Gate 1 — Flask request-flow / tenant isolation: PASS
- Step 6 — embedding service: PASS
- Embedding normalization parity gate: PASS
- Step 7 — Qdrant runtime + Colab secret adapter: PASS
- Step 8 — Groq runtime + Colab secret adapter: PASS
- Step 9 — tenant-scoped Qdrant corpus loading: PASS
- Step 10 — canonical Dense + BM25 + RRF hybrid retrieval: PASS
- Step 11 — deterministic Query Analyzer V1: PASS
- Step 12 — tenant document catalog + entity registry: PASS
- Step 13 — entity-routed hybrid retrieval: PASS
- Step 14 — structured evidence verification: PASS
- Step 15 — grounded answer generation + clean `answer_question_v2`: PASS
- Step 16 — context-aware financial unit resolution: PASS
- Step 17 — clean V2 Flask compatibility adapter: PASS
- Step 18 — real Flask `test_client()` → clean V2 integration: PASS
- Step 19 — canonical V2 ingestion core + real tokenizer/Docling gate: PASS

## Core V2 engine status
Golden Cell 21 series is represented in clean modules:
- Cell 21A → document catalog / entity registry
- Cell 21B → query analyzer
- Cell 21C → entity-routed hybrid retrieval
- Cell 21C.1 → aggregate metric expansion parity
- Cell 21D → structured evidence verification
- Cell 21E → grounded answer generation / `answer_question_v2`
- Cell 21E.1 → context-aware unit resolution

### Critical live evidence
- Apple FY2025 total net sales: `$416,161 million`
- Tesla Q4 2025 total revenue: `$24,901 million`
- Comparison preserves both values and reporting-period warning.
- Ambiguous questions require clarification before LLM generation.
- Outside-corpus questions return no-answer without LLM generation.
- Runtime tenant mismatch fails closed before retrieval.
- No Step 7–19 validation modified live Qdrant points unless the test explicitly used an in-memory/fake client.

### Unit-resolution parity
- Apple selected evidence originally lacked explicit scale in the same chunk.
- Context-aware resolution recovered `USD millions` from weighted neighboring/source context.
- Live Apple scale scores: millions `93.0`, thousands `4.0`.
- Tesla preserved its already-explicit `USD millions` classification.

## Flask / web integration status
- Browser-controlled tenant/org values cannot override trusted membership tenant.
- Historical canonical Cell 22D did not exist as a saved notebook cell; the extracted clean regression is its replacement evidence, not a reconstructed historical cell.
- Step 17 adapter converts clean V2 source cards into the Flask `results` contract.
- Step 18 live PASS: login → trusted membership → `/ask` → clean V2 → rendered sources → `QueryLog`.
- Live filenames are registry-driven (`TSLA-Q4-2025-Update.pdf` in the current corpus), not hardcoded product behavior.
- Browser session/form tenant tampering could not change the trusted tenant selected by Flask.

## Ingestion status
- `src/vaultify/services/ingestion.py` now contains canonical PDF validation, SHA-256 hashing, Canonical Chunker V2, Docling conversion, deterministic point IDs, tenant/document Qdrant filters, safe replace-on-reindex behavior, and failure cleanup.
- Committed ingestion regressions PASS, including fake-Qdrant replace/cleanup behavior.
- A dedicated retokenization regression protects the oversized-table-row decode → re-tokenize edge case.
- Real MiniLM tokenizer live gate PASS with a maximum generated chunk size of exactly `240 / 240` tokens.
- Oversized table rows split safely; Markdown separator rows are removed; exact duplicate chunks are suppressed.
- Real Docling converter construction PASS.
- Step 19 live gate performed no Qdrant writes.

## Extracted runtime surface
- `src/vaultify/config.py`
- `src/vaultify/extensions.py`
- `src/vaultify/models/__init__.py`
- `src/vaultify/web/tenancy.py`
- `src/vaultify/web/app.py`
- `src/vaultify/web/answer_adapter.py`
- `src/vaultify/services/embeddings.py`
- `src/vaultify/services/qdrant.py`
- `src/vaultify/services/llm.py`
- `src/vaultify/services/retrieval.py`
- `src/vaultify/services/query_analyzer.py`
- `src/vaultify/services/document_catalog.py`
- `src/vaultify/services/entity_routing.py`
- `src/vaultify/services/evidence_verification.py`
- `src/vaultify/services/grounded_answer.py`
- `src/vaultify/services/unit_resolution.py`
- `src/vaultify/services/answer_service.py`
- `src/vaultify/services/ingestion.py`
- `tests/regression/`
- `notebooks/Vaultify_R1_Control_Panel.ipynb`

## Test-evidence boundary
- Committed pytest covers Flask request-flow security plus deterministic analyzer/catalog/routing/evidence/unit/adapter/Flask-V2/ingestion behavior.
- Live Colab regressions cover Qdrant/model-dependent behavior plus the real tokenizer/Docling ingestion gate.
- Long-lived Colab runtimes must reload changed modules after Git sync or restart the runtime.
- Fresh Colab setup now requires `filetype` and `docling` in addition to the previously extracted runtime/test dependencies.

## Intentionally not extracted / completed yet
- upload and full document-management routes
- ConnectorCredential release model
- OAuth
- MCP
- Cloudflare / tunnel runtime
- production persistence / migrations
- stable deployment configuration
- Phase 3.9 product work

## Next bounded unit
- Step 20 — clean Flask upload/document-management slice using the trusted organization/tenant path and the extracted ingestion service.

## Guardrails
- Golden notebook remains immutable.
- Do not redesign working retrieval, ingestion, OAuth, MCP, or security behavior during extraction.
- Split by responsibility, not arbitrary line count.
- Continue as one bounded extraction unit → regression → PASS/FAIL → next unit.
- Apple/Tesla remain regression fixtures; runtime services accept dynamic tenant data and registries.
- GitHub is source/control infrastructure, not the product goal.

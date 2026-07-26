# Vaultify Release State

## Current release track
- Target: Vaultify V0.1 Technical Preview
- Active branch: `release/v0.1-extraction`
- Golden baseline commit: `53eb736646ecf88c8551a490606014ed5307b6ae`
- Phase 3.8 historical milestone: CLOSED
- R1 Release Extraction: IN PROGRESS
- Remote reconciliation checkpoint: CLEAN / CONSISTENT THROUGH R1 STEP 22

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
- Step 20 — trusted Flask upload/document-management slice: PASS
- Step 21 — organization-scoped ConnectorCredential foundation: PASS
- Step 22 — credential-bound clean V2 connector bridge: PASS

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
- No Step 7–22 validation modified live Qdrant points unless explicitly using a live read-only gate; Steps 20–22 used no live Qdrant writes.

## Flask / web integration status
- Browser-controlled tenant/org values cannot override trusted membership tenant.
- Historical canonical Cell 22D did not exist as a saved notebook cell; the extracted clean regression is its replacement evidence, not a reconstructed historical cell.
- Step 17 adapter converts clean V2 source cards into the Flask `results` contract.
- Step 18 live PASS: login → trusted membership → `/ask` → clean V2 → rendered sources → `QueryLog`.
- Step 20 adds `/documents`, `/documents/upload`, retry, and delete through the trusted organization path.
- Upload duplicate protection is scoped by organization + document hash.
- Cross-organization retry/delete document IDs are rejected.
- Delete targets only the trusted tenant/document hash.
- Step 20 dedicated regression PASS and then-full extracted suite PASS: `28 passed`.

## Ingestion status
- `src/vaultify/services/ingestion.py` contains canonical PDF validation, SHA-256 hashing, Canonical Chunker V2, Docling conversion, deterministic point IDs, tenant/document Qdrant filters, safe replace-on-reindex behavior, and failure cleanup.
- Dedicated retokenization regression protects the oversized-table-row decode → re-tokenize edge case.
- Real MiniLM tokenizer live gate PASS with maximum generated chunk size exactly `240 / 240` tokens.
- Real Docling converter construction PASS.
- Step 19 live gate performed no Qdrant writes.

## Connector credential / V2 status
- `ConnectorCredential` belongs to `Organization`; tenant identity is derived from that trusted organization.
- Only SHA-256 token hashes plus a safe display prefix are persisted; plaintext connector tokens are not stored.
- Active lookup, unknown-token rejection, revocation, rotation, and `last_used_at` tracking are extracted.
- Step 21 dedicated regression PASS and full extracted regression suite PASS: `29 passed`.
- `src/vaultify/services/connector_answer.py` binds raw connector token → active credential → organization tenant → explicit tenant runtime → clean `answer_question_v2`.
- The connector caller cannot supply `tenant_id` or `organization_id`.
- Apple and Tesla credentials can resolve different trusted runtimes.
- Unknown/revoked credentials fail before runtime resolution/retrieval.
- Runtime tenant mismatch fails before V2 execution.
- Step 22 dedicated regression PASS and full extracted regression suite PASS: `30 passed`.

## Extracted runtime surface
- `src/vaultify/config.py`
- `src/vaultify/extensions.py`
- `src/vaultify/models/__init__.py`
- `src/vaultify/web/tenancy.py`
- `src/vaultify/web/app.py`
- `src/vaultify/web/answer_adapter.py`
- `src/vaultify/web/documents.py`
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
- `src/vaultify/services/connector_credentials.py`
- `src/vaultify/services/connector_answer.py`
- `src/vaultify/templates/documents.html`
- `src/vaultify/templates/upload.html`
- `tests/regression/`
- `notebooks/Vaultify_R1_Control_Panel.ipynb`

## Test-evidence boundary
- Committed pytest covers Flask security plus deterministic analyzer/catalog/routing/evidence/unit/adapter/Flask-V2/ingestion/document-management/credential/connector-V2 behavior.
- Live Colab regressions cover Qdrant/model-dependent behavior plus the real tokenizer/Docling ingestion gate.
- Long-lived Colab runtimes must reload changed modules after Git sync or restart the runtime.

## Intentionally not extracted / completed yet
- authenticated MCP request layer / `ask_documents`
- OAuth Authorization Server / PKCE / DCR
- OAuth-protected MCP
- Cloudflare / public external acceptance runtime
- production persistence / migrations
- stable deployment configuration
- Phase 3.9 product work

## Next bounded unit
- Step 23 — authenticated MCP request layer: HTTP Bearer token → fail-closed TokenVerifier → request auth context → credential-bound clean V2 `ask_documents`; client-controlled tenant/org arguments and tenant/org response metadata remain absent.

## Guardrails
- Golden notebook remains immutable.
- Do not redesign working retrieval, ingestion, OAuth, MCP, or security behavior during extraction.
- Do not reintroduce Cell 23C global tenant swapping; release V2 uses explicit tenant/runtime dependencies.
- Do not expose tenant or organization identity in the public MCP tool contract.
- Split by responsibility, not arbitrary line count.
- Continue as one bounded extraction unit → regression → PASS/FAIL → next unit.
- Apple/Tesla remain regression fixtures; runtime services accept dynamic tenant data and registries.
# Vaultify Release State

## Current release track
- Target: Vaultify V0.1 Technical Preview
- Active branch: `release/v0.1-extraction`
- Golden baseline commit: `53eb736646ecf88c8551a490606014ed5307b6ae`
- Phase 3.8 historical milestone: CLOSED
- R1 Release Extraction: IN PROGRESS
- Remote reconciliation checkpoint: CLEAN / CONSISTENT THROUGH R1 STEP 23

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
- Step 23 — authenticated MCP request layer / `ask_documents`: PASS

## Core V2 engine status
Golden Cell 21 series is represented in clean modules:
- Cell 21A → document catalog / entity registry
- Cell 21B → query analyzer
- Cell 21C → entity-routed hybrid retrieval
- Cell 21C.1 → aggregate metric expansion parity
- Cell 21D → structured evidence verification
- Cell 21E → grounded answer generation / `answer_question_v2`
- Cell 21E.1 → context-aware unit resolution

### Critical evidence
- Apple FY2025 total net sales: `$416,161 million`
- Tesla Q4 2025 total revenue: `$24,901 million`
- Comparison preserves both values and reporting-period warning.
- Ambiguous questions require clarification before LLM generation.
- Outside-corpus questions return no-answer without LLM generation.
- Runtime tenant mismatch fails closed before retrieval.
- Steps 20–23 performed no live Qdrant writes.

## Flask / ingestion status
- Browser-controlled tenant/org values cannot override trusted membership tenant.
- Historical canonical Cell 22D did not exist as a saved notebook cell; extracted regression is replacement evidence only.
- Step 18 live PASS: login → trusted membership → `/ask` → clean V2 → rendered sources → `QueryLog`.
- Step 20 adds trusted `/documents`, upload, retry, and delete; cross-org document IDs are rejected.
- `src/vaultify/services/ingestion.py` contains canonical PDF validation, SHA-256 hashing, Canonical Chunker V2, Docling conversion, deterministic point IDs, tenant/document filters, safe replace-on-reindex, and failure cleanup.
- Real MiniLM tokenizer gate PASS at exactly `240 / 240` tokens; real Docling converter construction PASS.

## Connector / MCP status
- `ConnectorCredential` belongs to `Organization`; tenant identity is derived from that organization.
- Only SHA-256 connector-token hashes plus a safe display prefix are persisted; plaintext connector tokens are not stored.
- Active lookup, unknown-token rejection, revocation, rotation, and `last_used_at` tracking are extracted.
- Step 21 full suite: `29 passed`.
- `connector_answer.py` binds connector token → active credential → trusted tenant → explicit tenant runtime → clean V2.
- Caller cannot supply `tenant_id` or `organization_id`; runtime mismatch fails before V2.
- Step 22 full suite: `30 passed`.
- `mcp/server.py` builds an authenticated Streamable HTTP MCP resource server with fail-closed Bearer verification.
- Public `ask_documents` exposes only `question`; tenant/org metadata and raw chunk text are absent from public output.
- Missing/unknown/revoked Bearer credentials are rejected at the MCP request layer.
- Apple and Tesla credentials reach different trusted tenants.
- Step 23 dedicated regression PASS and full extracted suite PASS: `31 passed`.

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
- `src/vaultify/mcp/server.py`
- `src/vaultify/templates/documents.html`
- `src/vaultify/templates/upload.html`
- `tests/regression/`
- `notebooks/Vaultify_R1_Control_Panel.ipynb`

## Test-evidence boundary
- Committed pytest covers Flask security and deterministic V2/ingestion/document/credential/connector/MCP behavior.
- Live Colab gates cover Qdrant/model-dependent behavior plus real tokenizer/Docling ingestion.
- Long-lived Colab runtimes must sync/reload changed modules or restart.

## Intentionally not extracted / completed yet
- OAuth Authorization Server / PKCE / DCR / refresh rotation / OAuth revocation
- OAuth-protected MCP access-token verifier
- Cloudflare / public external acceptance runtime
- production persistence / migrations
- stable deployment configuration
- Phase 3.9 product work

## Next bounded unit
- Step 24 — extract the OAuth Authorization Server protocol core proven in golden Cell 23H: metadata, Dynamic Client Registration, Authorization Code + PKCE S256, short-lived access tokens, rotating refresh tokens, revocation, and connector-bound authorization identity. Product code must use an injected state-store interface; an in-memory store may be used only by regression tests until R2 persistence.

## Guardrails
- Golden notebook remains immutable.
- Do not redesign working retrieval, ingestion, OAuth, MCP, or security semantics during extraction.
- Do not reintroduce Cell 23C global tenant swapping; release V2 uses explicit tenant/runtime dependencies.
- Do not expose tenant or organization identity in the public MCP tool contract.
- Do not make in-memory OAuth state the final release persistence layer.
- Do not add Quick Tunnel/thread launcher code to application modules.
- Continue one bounded extraction unit → regression → PASS/FAIL → next unit.
- Apple/Tesla remain regression fixtures; runtime services accept dynamic tenant data and registries.

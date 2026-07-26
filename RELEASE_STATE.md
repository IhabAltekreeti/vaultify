# Vaultify Release State

## Current release track
- Target: Vaultify V0.1 Technical Preview
- Active branch: `release/v0.1-extraction`
- Golden baseline commit: `53eb736646ecf88c8551a490606014ed5307b6ae`
- Phase 3.8 historical milestone: CLOSED
- Phase 3.8 extracted release-parity acceptance: CLOSED
- R1 Release Extraction: FINALIZATION / AUDIT
- Remote reconciliation checkpoint: CLEAN / CONSISTENT THROUGH R1 STEP 28

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
- Step 7 — Qdrant runtime + secret boundary: PASS
- Step 8 — Groq runtime + secret boundary: PASS
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
- Step 24 — OAuth Authorization Server protocol core: PASS
- Step 25 — OAuth-protected MCP resource binding: PASS
- Step 26 — public OAuth + MCP live acceptance against real Apple V2 runtime: PASS
- Step 27 — real external Claude OAuth/MCP validation: PASS
- Step 28 — final revoke / cleanup / Phase 3.8 acceptance audit: PASS

## Core V2 evidence
- Apple FY2025 total net sales: `$416,161 million`
- Tesla Q4 2025 total revenue: `$24,901 million`
- Comparison preserves both values and reporting-period warning.
- Ambiguous questions require clarification before LLM generation.
- Outside-corpus questions return no-answer without LLM generation.
- Runtime tenant mismatch fails closed before retrieval.
- Steps 20–28 performed no live Qdrant writes.

## Connector / MCP / OAuth evidence
- `ConnectorCredential` belongs to `Organization`; tenant identity is derived from that trusted organization.
- Only SHA-256 connector-token hashes plus a safe display prefix are persisted; plaintext connector tokens are not stored.
- Caller cannot supply `tenant_id` or `organization_id`; runtime mismatch fails before V2.
- Step 21 full suite: `29 passed`; Step 22: `30 passed`; Step 23: `31 passed`.
- `oauth/store.py` defines an injected persistence boundary; R1 product code owns no global in-memory OAuth database.
- `oauth/server.py` preserves DCR, Authorization Code, PKCE S256, short-lived access tokens, rotating refresh tokens, and revocation.
- OAuth authorization-code/access-token/refresh-token secrets are stored only by SHA-256 hash.
- Step 24 full suite: `32 passed`.
- `mcp/oauth_server.py` binds OAuth access tokens to the exact MCP resource and trusted connector identity.
- Wrong-resource / revoked credentials fail closed before retrieval.
- Apple and Tesla OAuth grants resolve different trusted tenants.
- Tenant/org metadata and raw chunk text remain absent from public MCP output.
- Step 25 dedicated regression + full extracted suite: `33 passed`.

## Public / real-Claude acceptance evidence
- Public OAuth metadata: PASS.
- Public MCP protected-resource metadata: PASS.
- Public DCR + PKCE S256: PASS.
- Real public `ask_documents`: `$416,161 million`, `apple_fy2025_10k.pdf`, `Note 2 - Revenue`.
- Real Qdrant corpus load observed 745 Apple chunks; read-only.
- Real Claude completed Vaultify OAuth, discovered/invoked `ask_documents`, and returned the expected value/source.
- Initial immediate MCP client startup race was isolated; the same live runtime passed without rebuild/restart. A control-layer readiness helper now exists for future runs.
- Temporary OAuth consent page is acceptance-only protocol UI, not the final product UX.

## Step 28 cleanup evidence
- An already-issued temporary OAuth access token worked before revocation.
- Backing temporary ConnectorCredential was revoked.
- The same OAuth token was rejected after ConnectorCredential revocation.
- Acceptance-only OAuth clients/codes/access/refresh state was cleared.
- Temporary OAuth + MCP Uvicorn servers were stopped.
- Both Cloudflare Quick Tunnels were stopped.
- Temporary token references were cleared from notebook memory.
- Final extracted regression gate: `33 passed in 4.53s`.
- No live Qdrant points were modified.

## Extracted runtime surface
- `src/vaultify/config.py`
- `src/vaultify/extensions.py`
- `src/vaultify/models/`
- `src/vaultify/web/`
- `src/vaultify/services/`
- `src/vaultify/mcp/server.py`
- `src/vaultify/mcp/oauth_server.py`
- `src/vaultify/oauth/store.py`
- `src/vaultify/oauth/server.py`
- `src/vaultify/templates/`
- `tests/regression/`
- `notebooks/Vaultify_R1_Control_Panel.ipynb`
- `scripts/phase38_public_acceptance.py` (temporary acceptance harness only)
- `scripts/phase38_public_readiness.py` (temporary readiness helper only)

## R1 finalization still required
- Run the structural / forbidden-runtime scan across product modules; this has NOT been claimed as done yet.
- Run final package/import/repository hygiene audit.
- Confirm acceptance-only tunnel/thread/in-memory OAuth helpers remain outside the product runtime boundary.
- Freeze/archive the migration control notebook as completed extraction evidence.
- Create the new short clean V0.1 control notebook that imports the modular repo instead of embedding product source.

## After R1 closes
- R2 — production persistence / migrations, including OAuth state persistence.
- R3 — stable deployment configuration/runtime.
- R4 — minimal Phase 3.9 UX/product work, including branded authorization UI and preservation/porting of useful golden-notebook UI elements.
- R5 — Phase 3.10 security/regression hardening.
- V0.1 Technical Preview acceptance.

## Next bounded unit
- Step 29 — R1 closure audit only: structural forbidden-runtime scan + package/import/repository hygiene. Do not add new product features. If PASS, archive this migration notebook and move to the clean V0.1 control notebook.

## Guardrails
- Golden notebook remains immutable.
- Do not redesign working retrieval, ingestion, OAuth, MCP, or security semantics during extraction.
- Do not reintroduce Cell 23C global tenant swapping; release V2 uses explicit tenant/runtime dependencies.
- Do not expose tenant or organization identity in the public MCP tool contract.
- Do not make in-memory OAuth state the final release persistence layer.
- Do not add Quick Tunnel/thread launcher code to application modules.
- Split by responsibility, not arbitrary line count.
- Apple/Tesla remain regression fixtures; runtime services accept dynamic tenant data and registries.

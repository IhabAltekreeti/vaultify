# Vaultify Release State

## Current release track

- Target: Vaultify V0.1 Technical Preview
- Active branch: `release/v0.1-extraction`
- Golden baseline commit: `53eb736646ecf88c8551a490606014ed5307b6ae`
- Phase 3.8: CLOSED
- R1 Release Extraction: IN PROGRESS

## R1 completed steps

- R1 Step 1 — stable non-secret config extraction: PASS
- R1 Step 2 — shared Flask extensions extraction: PASS
- R1 Step 3 — core web models extraction: PASS
- R1 Step 4 — trusted membership / tenant resolution: PASS
- R1 Step 5 — minimal Flask auth + `/ask` slice: PASS

## Early security gate

- `tests/regression/test_flask_request_flow.py`: PASS
- Latest observed result: `1 passed`
- Real `Flask.test_client()` path is covered.
- Unauthenticated `/ask` redirects to login.
- Valid login works.
- Empty questions are rejected before answer service invocation.
- Answered, clarification, and no-answer outputs render through the real Flask route.
- `QueryLog` persists accepted questions against the authenticated user and organization.
- Logout clears authentication.
- Browser-controlled `tenant_id` and unauthorized `organization_id` cannot override the tenant derived from authenticated organization membership.

## Flask evidence-gap status

The earlier missing canonical Cell 22D / stale `FLASK_REQUEST_FLOW_REGRESSION_PASSED` evidence gap is now CLOSED for the extracted codebase by the deterministic Flask request-flow regression above.

This test does not prove live Qdrant/Groq/V2 retrieval behavior; those remain separate integration regressions.

## Extracted runtime surface so far

- `src/vaultify/config.py`
- `src/vaultify/extensions.py`
- `src/vaultify/models/__init__.py`
- `src/vaultify/web/__init__.py`
- `src/vaultify/web/tenancy.py`
- `src/vaultify/web/app.py`
- `src/vaultify/templates/login.html`
- `src/vaultify/templates/dashboard.html`
- `tests/regression/test_flask_request_flow.py`

## Intentionally not extracted yet

- Qdrant client/runtime
- Groq client/runtime
- embeddings
- retrieval / reranking / evidence engine
- ingestion / Docling / OCR
- OAuth
- MCP
- ConnectorCredential release model
- Cloudflare / tunnel runtime
- upload and document-management routes
- production deployment configuration

## Guardrails

- Golden notebook remains immutable behavioral reference.
- Do not recreate or edit historical Cell 22D.
- No Phase 3.9 product work during R1 extraction.
- No broad redesign while extracting canonical behavior.
- Continue with one bounded extraction step followed by regression PASS/FAIL before the next step.

# Vaultify — Current Project State

Last updated: 2026-08-23

## Purpose
Vaultify is a multi-tenant RAG / document-intelligence SaaS prototype built around tenant-isolated document retrieval and grounded answers.

## Source of truth
- Repository: `IhabAltekreeti/vaultify`
- Active development branch: `release/v0.1-extraction`
- Product source: `src/vaultify/`
- Golden notebook and historical notebooks are evidence/snapshots, not the product source of truth.
- The golden notebook remains immutable.

## Proven core
- document ingestion
- Docling / RapidOCR parsing
- embeddings with `sentence-transformers/all-MiniLM-L6-v2`
- Qdrant retrieval
- dense + BM25 + RRF hybrid retrieval
- query analysis
- entity routing
- structured evidence verification
- grounded answers with source evidence
- context-aware unit resolution
- Flask authentication and tenant resolution
- tenant isolation
- MCP `ask_documents`
- OAuth 2.0 / PKCE / DCR
- real external Claude → OAuth → MCP → `ask_documents` acceptance

Core invariant:
> The client must never choose the tenant.

## Canonical evidence
- Apple FY2025 Net Sales: `$416,161 million`
- Tesla Q4 2025 Total Revenue: `$24,901 million`
- R1 extracted regression gate: `33 passed in 4.53s`
- R1 structural/package/repository hygiene audit: PASS
- No live Qdrant points were modified during the R1 closure audit.

## Current LLM state
Retired model:
`llama-3.3-70b-versatile`

Current source configuration:
`openai/gpt-oss-120b`

Isolated live model checks:
- `openai/gpt-oss-120b` → PASS; returned model: `openai/gpt-oss-120b`
- `openai/gpt-oss-20b` → PASS; returned model: `openai/gpt-oss-20b`

These isolated checks are not full Vaultify canonical regression. Full Apple/Tesla/ambiguity/no-answer/MCP validation remains the migration acceptance gate.

## External services
- Groq: runtime LLM provider
- Qdrant Cloud: vector store
- OAuth / MCP: integration layer

Qdrant was suspended after inactivity but has been reactivated. Do not recreate or change the cluster unless explicitly required.

## Release position
R1 Release Extraction is CLOSED.

Next stages:
- R2: PostgreSQL, Alembic, persistent OAuth state, object storage.
- R3: stable HTTPS deployment, resource benchmarking, production CUDA review.
- R4: branded OAuth, dashboard, documents, upload, Ask Vaultify, connector management.
- R5: deployed regression and security hardening: tenant isolation, IDOR, auth, leakage, MCP, OAuth.
- V0.1 Technical Preview acceptance.

## Known R2/R3 debt
- development Flask secret
- in-memory SQLite default
- `SESSION_COOKIE_SECURE=False` development default
- production persistence/deployment not final

## Guardrail
Do not redesign proven retrieval, ingestion, embeddings, Qdrant, tenant isolation, MCP, or OAuth without evidence of a real defect or requirement.

Engineering rule:
`PROVEN SYSTEM → MINIMUM CHANGE → REGRESSION → NEXT STEP`

# Vaultify — Current State & Architecture

**Last Updated:** 2026-08-24  
**Release Stage:** R1 CLOSED / R2 IN PROGRESS  
**Repository:** `IhabAltekreeti/vaultify`  
**Branch:** `release/v0.1-extraction`  

---

## 1. Project Overview
Vaultify is a multi-tenant document intelligence and grounded RAG SaaS platform. Organizations upload private PDFs, Vaultify parses, chunks, and indexes them with tenant metadata isolation in Qdrant Cloud, and authorized users or external AI agents (like Claude via OAuth-protected MCP) query the documents with verifiable source citations.

---

## 2. Core Invariants (Non-Negotiable)
1. **The client must never choose or supply the tenant ID.** Tenant identity is strictly derived from the authenticated user's organization membership or verified connector token.
2. **Zero Plaintext Bearer Tokens.** Connector tokens and OAuth secrets are stored exclusively as SHA-256 hashes.
3. **No Hallucination on Missing Evidence.** Ambiguous queries trigger `clarification_required` and out-of-corpus queries return `no_answer` without invoking the LLM.
4. **Token Ceiling Enforcement.** Canonical Chunker V2 enforces a strict $\le 240$ token ceiling per chunk with table row/column structure preservation.

---

## 3. Technology Stack & Configuration
| Component | Technology | Configuration / Version |
|---|---|---|
| Language | Python | 3.11 / 3.13 |
| Web Framework | Flask | Flask-Login, Flask-SQLAlchemy, Flask-WTF |
| Database (Current) | SQLite | In-memory / dev (R2 target: PostgreSQL) |
| Vector Database | Qdrant Cloud | Collection: `vaultify_v3_documents` |
| Embedding Model | Sentence Transformers | `all-MiniLM-L6-v2` (384 dimensions) |
| LLM Provider | Groq Cloud | `openai/gpt-oss-120b` (~500 tps, 131k context) |
| External AI Protocol | Model Context Protocol | FastMCP (`mcp<2`), OAuth 2.0 (PKCE S256, DCR) |
| Parser | Docling / RapidOCR | PDF parsing with table extraction |

---

## 4. Current Milestone Status
- [x] **R0 (Phase 3.8 Seal):** Closed.
- [x] **R1 (Release Extraction & All-In-One):** Closed (33/33 tests passed in 4.53s).
- [ ] **R2 (Production Persistence):** In Progress (PostgreSQL, Object Storage, Migrations).
- [ ] **R3 (Stable Deployment):** Planned.
- [ ] **R4 (Minimal V1 UX):** Planned.
- [ ] **R5 (Deployed Security & Regression Gate):** Planned.

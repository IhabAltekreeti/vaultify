# Vaultify Project Memory — Daily Log

## 2026-08-24 (Milestone: R1 Closed & Groq Model Migration)

### 1. Completed Work
1. **Groq Model Migration (V1-Blocking):**
   - Decommissioned `llama-3.3-70b-versatile` (shut down 2026-08-16) investigated on Groq API.
   - Evaluated candidate models: `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `qwen/qwen3.6-27b`.
   - Executed isolated live API test in Colab for `openai/gpt-oss-120b` and `openai/gpt-oss-20b`: STATUS PASS.
   - Executed live grounded answer test for Apple canonical query with `openai/gpt-oss-120b`: Output verified exactly as `$416,161 million` with source `apple_fy2025_10k.pdf, Note 2 - Revenue`.
   - Updated `LLM_MODEL = "openai/gpt-oss-120b"` in `src/vaultify/config.py` on GitHub (`commit: 8b1c3e7`).

2. **All-In-One Notebook Assembly (Cells 0–13):**
   - Implemented clean `Cell 0` dependency setup with version pins (`mcp<2`, `filetype`, `flask-login`, etc.).
   - Verified `Cell 1` (Contract), `Cell 2` (Sync), `Cell 3` (Architecture Map), `Cell 4` (Dependencies), `Cell 5` (External Inventory).
   - Fixed regex parsing in `Cell 6` (Secrets & Config Boundary Audit) -> `CELL 6 PASS`.
   - Verified `Cell 7` (Config, Extensions, ORM Models) -> `CELL 7 PASS`.
   - Verified `Cell 8` (Embeddings 384d, Qdrant Cloud, Groq Client) -> `CELL 8 PASS`.
   - Verified `Cell 9` (Canonical Chunker V2, 240 token ceiling, Document Catalog) -> `CELL 9 PASS`.
   - Verified `Cell 10` (Hybrid Retrieval, Entity Routing, Evidence Verification, Grounded Answer - 5 Golden Behaviors) -> `CELL 10 PASS`.
   - Verified `Cell 11` (Flask Web App, Login/Logout, Multi-Tenancy Isolation, /ask POST flow) -> `CELL 11 PASS`.
   - Verified `Cell 12` (Connector Credential Token Lifecycle, SHA-256 Hash Storage, Revocation, Rotation, MCP/OAuth Boundaries) -> `CELL 12 PASS`.
   - Executed `Cell 13` (Final Regression Test Suite) -> **All 17 modules, 33 tests passed in 4.53s**.

3. **Milestone R1 Closure:**
   - R1 Release Extraction is officially **CLOSED and SEALED**.

### 2. Files Modified / Created
- `src/vaultify/config.py`: Updated `LLM_MODEL = "openai/gpt-oss-120b"`.
- `RELEASE_STATE.md`: Updated to record R1 closure and R2 in-progress.
- `docs/project-memory/DAILY_LOG.md`: Initialized daily operational memory log.
- `docs/project-memory/CURRENT_STATE.md`: Initialized canonical architecture state.

### 3. Decisions & Guardrails Confirmed
- Model choice: `openai/gpt-oss-120b` on Groq Developer/Free tier.
- Dependencies: Standardized `mcp<2` to preserve proven FastMCP 1.0 architecture without breaking changes.
- Invariant: Client never supplies or overrides `tenant_id`.
- Memory protocol: GitHub repository memory files are the source of truth across AI sessions.

### 4. Next Step
- Begin **Phase R2 — Production Persistence**:
  1. PostgreSQL database integration (`DATABASE_URL`).
  2. Alembic / Flask-Migrate migration schema.
  3. Persistent object storage abstraction for uploaded PDFs.
  4. Durable OAuth state store.

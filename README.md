# Vaultify v3 Rebuild

Vaultify is a multi-tenant document intelligence platform built with Flask, Docling, Sentence Transformers, Qdrant Cloud, Groq, and MCP.

This branch-ready checkpoint consolidates the working Colab prototype into a normal Python project. It preserves the verified Phase 1–3.5B behavior while removing the need to execute more than 65 notebook cells.

## Current verified capabilities

- PDF parsing with Docling
- Token-safe text and table chunking
- Normalized 384-dimensional embeddings
- Deterministic Qdrant point IDs
- Mandatory tenant filtering
- Grounded Groq answers
- Streamable HTTP MCP server
- User registration, login, logout, and hashed passwords
- Organizations, memberships, and role authorization
- Trusted tenant resolution from server-side membership
- Secure PDF validation and duplicate prevention
- Tenant-scoped ingestion with status transitions and retry support
- Dark responsive dashboard foundation

## Project structure

```text
app/
├── auth/
├── dashboard/
├── documents/
├── mcp/
├── organizations/
├── rag/
├── templates/
├── static/
├── authorization.py
├── models.py
└── rag_runtime.py
notebooks/
scripts/
tests/
run.py
run_mcp.py
requirements.txt
```

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set these secrets in the environment:

```text
QDRANT_URL
QDRANT_API_KEY
GROQ_API_KEY
VAULTIFY_SECRET_KEY
```

Run the web application:

```bash
python run.py
```

Run the tenant-bound MCP server:

```bash
export VAULTIFY_MCP_TENANT_ID=tenant_example
python run_mcp.py
```

The MCP client never supplies `tenant_id`. The tenant is fixed by trusted server configuration.

## Colab

Use `notebooks/Vaultify_Launch.ipynb`. It reduces startup to a small set of cells:

1. Clone and install
2. Load Colab Secrets
3. Start the web application
4. Open a Cloudflare Quick Tunnel
5. Optionally start MCP

## Security notes

- Never commit `.env`, API keys, SQLite databases, or uploaded PDFs.
- Quick Tunnels are development-only and temporary.
- Set `VAULTIFY_SECURE_COOKIES=1` behind production HTTPS.
- The current upload pipeline is synchronous; a production job queue remains on the roadmap.
- The current MCP runner is server-bound to one trusted tenant. Per-credential tenant resolution remains a later phase.

## Source checkpoint

The original development notebook and Python export are preserved under `notebooks/` for auditability and regression recovery.

# Vaultify — GPT → Spark Handoff Template

Use this template for bounded implementation tasks.

## STEP X — [TASK NAME]

**Owner:** GPT / USER / SPARK

**Approval status:**
- Approved by GPT: YES / NO
- If NO, Spark must not perform implementation.

### Goal
What must be achieved and why.

### Context / Evidence
Relevant current-state facts, previous test results, and project-memory references.

### Do
Exact operations Spark is authorized to perform.

### Do not touch
Explicit files, systems, architecture, services, or behaviors that must remain unchanged.

### Scope limits
What Spark must not expand into, even if it discovers related improvements.

### Tests / Evidence required
Exact tests, API calls, notebook cells, or inspections required.

### PASS criteria
Concrete observable conditions for success.

### FAIL / BLOCKED criteria
Conditions that must be reported instead of worked around silently.

### Required report
Spark must return `SPARK_OPERATION_REPORT.md` with all nine sections.

### Next-step rule
Spark must not execute the next task automatically. It must only recommend the next bounded step and identify whether GPT approval is required.

## Example

### STEP 1 — Isolated Groq model compatibility test

**Owner:** SPARK

**Approval status:** YES — test only; no source migration authorized.

**Goal:** Determine whether a selected Groq model can serve Vaultify's workload without changing source configuration or introducing paid billing.

**Do:**
- inspect current repository state
- use the approved runtime secret mechanism
- make isolated live model calls
- record returned model IDs and outputs
- test required canonical scenarios where explicitly requested

**Do not touch:**
- `src/vaultify/` configuration
- `LLM_MODEL`
- Qdrant
- embeddings
- retrieval
- MCP
- OAuth
- notebooks
- Git history

**PASS criteria:** Live runtime evidence is obtained and the requested scenarios pass with execution path identified where feasible.

**Next step:** Report only. Source migration requires a separate GPT-approved task.

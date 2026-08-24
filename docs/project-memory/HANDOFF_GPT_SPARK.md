# GPT ↔ Spark Handoff

## Roles
### GPT
- technical architect
- decision maker
- planner
- reviewer
- regression interpreter

### USER
- operator between AIs
- transfers GPT plans to Spark
- brings Spark evidence back to GPT

### Gemini Spark Agent
- implementation engineer
- repository inspection
- file search/read
- tests
- Colab execution when needed
- small controlled changes
- regression runs
- reporting

Spark is not the architectural decision maker.

## Required workflow
`GPT → PLAN → USER → SPARK → IMPLEMENT → USER → GPT REVIEW → NEXT STEP`

The next step reported by Spark is a recommendation only. Spark must not execute it automatically unless a new task explicitly authorizes it.

## Every GPT operational instruction must state the owner
Use:
- `Sorumlu: GPT`
- `Sorumlu: BEN`
- `Sorumlu: SPARK`

For Spark tasks specify scope, files, exclusions, expected output, evidence requirements, and PASS criteria.

## Standard task format
### STEP X — [WORK]
**Owner:** GPT / USER / SPARK

**Approval status:**
...

**Goal:**
...

**Context / Evidence:**
...

**Do:**
...

**Do not touch:**
...

**Scope limits:**
...

**Tests / Evidence required:**
...

**PASS criteria:**
...

**FAIL / BLOCKED criteria:**
...

**Required report:**
`docs/project-memory/format/SPARK_OPERATION_REPORT.md`

## Mandatory Spark operation report
Every Vaultify operation must use `SPARK_OPERATION_REPORT.md` and include all nine sections:

1. NE YAPTIM?
2. NEDEN YAPTIM?
3. NEREYE DOKUNDUM?
4. GITHUB DURUMU
5. TEST / KANIT
6. BULGULAR
7. SINIRLAMALAR / BELİRSİZLİKLER
8. SONUÇ
9. SONRAKİ ADIM

The report must distinguish facts from assumptions and must end with exactly one primary status: `PASS`, `FAIL`, `BLOCKED`, or `NOT TESTED`.

Short "done" summaries are not sufficient.

## Execution guardrails

- Establish branch/HEAD and relevant current state before material changes.
- Do not modify proven architecture without an explicitly approved bounded task.
- Do not expand scope to unrelated improvements.
- Do not commit/push unless explicitly authorized.
- Never commit secrets or credentials.
- Never weaken tests to obtain PASS.
- If evidence is insufficient, report the limitation instead of guessing.
- If a requested operation conflicts with project memory, stop and report the conflict.

Protected proven areas unless explicitly approved:
- retrieval
- Qdrant
- embeddings
- ingestion
- tenant isolation
- MCP
- OAuth
- authentication/authorization

## Migration protocol

For provider/model migrations:

`DISCOVER → ISOLATED TEST → EVIDENCE → GPT REVIEW → SOURCE CHANGE → REGRESSION`

Do not modify source configuration before compatibility evidence and GPT approval exist.

An isolated model response is not proof of full Vaultify compatibility.

## Evidence / fallback rule

When deterministic fallback, static responses, caching, or another non-LLM path can produce the expected answer, a generic PASS is insufficient.

Where feasible, report:
- `PASS — LLM-generated`
- `PASS — deterministic fallback`
- `FAIL`
- `BLOCKED`
- `NOT TESTED`

If execution path cannot be distinguished, state that explicitly.

## Source-of-truth rule

GitHub extracted source is authoritative:
`src/vaultify/`

Golden and historical notebooks are evidence/snapshots, not product source of truth.

The golden notebook remains immutable unless explicitly authorized.

Notebook synchronization follows:
`source → test → notebook`

## Memory files

Persistent project memory lives under:
`docs/project-memory/`

Operational/format rules live under:
`docs/project-memory/format/`

Key files:
- `CURRENT_STATE.md`
- `DECISIONS.md`
- `TODO.md`
- `REGRESSION.md`
- `HANDOFF_GPT_SPARK.md`
- `CHANGELOG.md`
- `format/SPARK_OPERATION_REPORT.md`
- `format/SPARK_EXECUTION_RULES.md`
- `format/GPT_SPARK_HANDOFF_TEMPLATE.md`

## Review protocol
After Spark reports results, GPT classifies them as correct, incomplete, wrong, blocked, or architectural overreach and determines the next bounded step.

## Decision authority
Spark may discover problems and propose alternatives, but it must not treat its own proposal as an approved architectural decision.

If an architectural change is not explicitly authorized, report it and stop before implementation.

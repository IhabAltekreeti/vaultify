# Vaultify — Spark Execution Rules

These rules govern Gemini Spark Agent operations in the Vaultify repository.

## 1. Roles

### GPT
- technical architect
- decision maker
- planner
- architecture reviewer
- regression/evidence reviewer

### USER
- operator between GPT and Spark
- transfers approved tasks
- provides Spark evidence back to GPT

### SPARK
- implementation engineer
- repository/file inspection
- controlled edits
- test execution
- Colab execution when explicitly requested
- regression execution
- evidence reporting

Spark does not independently approve architecture, migrations, redesigns, or production changes.

## 2. Mandatory operating loop

`GPT → PLAN → USER → SPARK → IMPLEMENT/TEST → USER → GPT REVIEW → NEXT STEP`

A reported next step is a recommendation, not permission to execute it.

## 3. Before changing anything

Spark must first establish, where applicable:
1. repository and branch
2. current HEAD
3. relevant files
4. current test/regression evidence
5. exact task scope
6. explicit exclusions

If the task is ambiguous or conflicts with project memory, stop and report the ambiguity.

## 4. Minimum-change rule

Use:

`PROVEN SYSTEM → MINIMUM CHANGE → REGRESSION → NEXT STEP`

Do not redesign a proven component merely because another implementation appears cleaner.

Especially protected unless explicitly approved:
- retrieval
- Qdrant
- embeddings
- ingestion
- tenant isolation
- MCP
- OAuth
- authentication/authorization

## 5. Migration gate

For provider/model migrations:

`DISCOVER → ISOLATED TEST → EVIDENCE → GPT REVIEW → SOURCE CHANGE → REGRESSION`

Do not change source configuration before the compatibility evidence and GPT approval required by the task are present.

An isolated model response is not full Vaultify compatibility evidence.

## 6. Scope control

When a task names files or systems, do not expand the scope without approval.

If an unrelated defect is discovered:
- record it
- explain impact
- do not silently fix it unless the task explicitly permits it

## 7. Secrets and credentials

Never commit plaintext credentials, API keys, tokens, cookies, or secrets.
Do not print secret values in reports.
Use masked evidence only when necessary.

## 8. Git safety

Unless the task explicitly authorizes Git operations:
- do not commit
- do not push
- do not rewrite history
- do not delete branches/files

If commit/push is authorized, report exact branch and commit SHA.

## 9. Notebook rule

GitHub extracted source is authoritative.
Golden and historical notebooks are evidence/snapshots, not source of truth.
Do not modify the golden notebook unless explicitly authorized.

Notebook synchronization must follow source → test → notebook, not notebook → source.

## 10. Evidence and fallback rule

A correct-looking answer is not sufficient proof when deterministic fallback exists.
Where technically possible, identify whether the result came from:
- live LLM
- deterministic fallback
- cached/static result
- unknown execution path

If the path cannot be distinguished, report the limitation.

## 11. Test integrity

Do not weaken, delete, skip, or rewrite tests merely to obtain PASS.
If a test fails because of an environment/dependency issue, report it as BLOCKED/FAIL according to the actual evidence.

## 12. Reporting

Every operation must use `SPARK_OPERATION_REPORT.md`.
The report must contain all nine sections and must end with one of:
- PASS
- FAIL
- BLOCKED
- NOT TESTED

## 13. Stop conditions

Stop and report instead of proceeding when:
- required credentials are unavailable
- the requested model/provider is unclear
- the task would change protected architecture without approval
- the requested file does not exist
- current state conflicts with project memory
- a destructive action is requested without explicit authorization
- evidence is insufficient to claim the requested PASS

## 14. Communication rule

Do not merely say "done".
Explain what happened, why it happened, what was touched, what proves it, what remains uncertain, and what should happen next.

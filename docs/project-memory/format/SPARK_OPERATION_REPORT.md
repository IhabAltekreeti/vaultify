# Vaultify — Spark Mandatory Operation Report

This format is mandatory for every Vaultify operation performed by Gemini Spark Agent.

Do not provide only a short result summary. Report what was actually inspected, changed, tested, and proven.

## 1. NE YAPTIM?

Describe the actual operations performed, in order.
Include commands, API calls, repository inspections, file reads, edits, tests, and other material actions.

## 2. NEDEN YAPTIM?

For each important operation, explain the technical reason.
Reference the applicable GPT-approved task, PASS criterion, decision, or project-memory rule.
Do not invent architectural justification after the fact.

## 3. NEREYE DOKUNDUM?

### Files read
List relevant files inspected.

### Files changed
List every modified, created, renamed, or deleted file.

If none were changed, explicitly write:
`No files changed.`

Also state whether any external service state was changed (for example Qdrant, Groq settings, OAuth configuration, or secrets).

## 4. GITHUB DURUMU

Report:
- branch
- HEAD before operation
- HEAD after operation, if applicable
- working tree status, if available
- commit created? yes/no
- commit SHA, if created
- push performed? yes/no
- remote/branch affected

Never imply that a local change was committed or pushed unless it actually was.

## 5. TEST / KANIT

List every relevant command, API request, notebook cell, or test executed.
Show real outputs where practical.
For each test state:
- PASS
- FAIL
- BLOCKED
- NOT TESTED

Never convert an unexecuted check into a PASS based on documentation or expectation.

## 6. BULGULAR

Separate:
- directly observed/proven facts
- API/runtime evidence
- repository evidence
- documentation-only information
- assumptions/inferences

For model tests, report the actual returned model ID when available.

## 7. SINIRLAMALAR / BELİRSİZLİKLER

Explicitly state anything that could not be tested.
Distinguish estimated/documentation behavior from live runtime behavior.
If deterministic fallback may have produced a result, say so.
If the execution path cannot distinguish fallback from LLM output, say so rather than claiming LLM validation.

## 8. SONUÇ

End with exactly one primary status:

`PASS — ...`

or

`FAIL — ...`

or

`BLOCKED — ...`

or

`NOT TESTED — ...`

The status must describe the actual scope tested, not a broader untested claim.

## 9. SONRAKİ ADIM

Do not execute the next step automatically.
Only recommend the next bounded operation.
Identify whether GPT approval is required before it can be performed.

If there is a decision point, state it explicitly.

## Evidence discipline

- Do not claim a file was changed unless it was actually changed.
- Do not claim a test was run unless it was actually run.
- Do not claim an API model is accessible merely because documentation lists it.
- Do not claim a migration is compatible merely because an isolated model call succeeds.
- Do not hide blockers behind a summary.

## Architecture guardrail

Spark is the implementation engineer, not the architectural decision maker.
Do not perform an unapproved migration, redesign, provider change, or production-impacting change.
Proven Vaultify components must remain unchanged unless the approved task explicitly requires a minimum scoped change backed by evidence.

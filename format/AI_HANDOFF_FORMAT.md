# AI Handoff Format

Use this when transferring work between GPT, the user, and Spark.

## 1. What happened?
Short plain-language summary.

## 2. Why?
Reason the action was taken.

## 3. Evidence
Exact tests, outputs, commit SHA, branch, or file paths.

## 4. What changed?
List changed files and scope. If nothing changed, say so explicitly.

## 5. What did not change?
List protected components.

## 6. Decision
PASS / FAIL / BLOCKED / NEEDS REVIEW.

## 7. Next bounded step
One concrete next operation with an explicit owner.

## 8. Do not assume
List claims that still need verification.

For Spark reports always include:
- branch
- HEAD commit
- files read
- files changed
- tests run
- test outputs
- blockers
- proposed next step

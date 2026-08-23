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

## Every GPT operational instruction must state the owner
Use:
- `Sorumlu: GPT`
- `Sorumlu: BEN`
- `Sorumlu: SPARK`

For Spark tasks specify scope, files, exclusions, expected output, and PASS criteria.

## Standard task format
### STEP X — [WORK]
**Owner:** GPT / USER / SPARK

**Goal:**
...

**Do:**
...

**Do not touch:**
...

**Expected output:**
...

**PASS criteria:**
...

## Spark report requirements
Always report:
- branch
- HEAD commit
- files read
- files changed
- tests run
- test outputs
- blockers
- proposed next step

## Review protocol
After Spark reports results, GPT classifies them as correct, incomplete, wrong, or architectural overreach and determines the next bounded step.

## Migration rule
Do not modify source before compatibility evidence exists. Do not let a model migration silently become a retrieval/Qdrant/embedding/MCP/OAuth redesign.

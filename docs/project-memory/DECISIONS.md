# Vaultify — Decisions

## Decision 001 — GitHub is the engineering source of truth
`src/vaultify/` is authoritative. Notebooks are snapshots, experiments, or acceptance evidence.

## Decision 002 — Golden notebook is immutable
Do not turn the golden notebook into the product runtime. Preserve it as historical evidence.

## Decision 003 — Minimum-change engineering
Proven components are not redesigned without evidence of a real defect or requirement.

## Decision 004 — Tenant security invariant
The client must never choose the tenant. Tenant identity must come from trusted server-side authentication, organization membership, or runtime context.

## Decision 005 — LLM migration is isolated
A provider/model migration is tested independently before changing source configuration. The first acceptance question is whether the selected Groq Free Tier model can serve the existing workload without payment.

## Decision 006 — No paid API usage
For the current development phase, do not add a payment method and do not intentionally use paid API billing, even for a tiny amount.

## Decision 007 — Groq remains the runtime provider
The migration is a model replacement inside Groq, not a move to OpenAI API or another provider.

## Decision 008 — Development AI and Vaultify runtime LLM are separate
The coding/development agent may be Gemini Spark or another engineering tool. That does not determine the model used by Vaultify at runtime.

## Decision 009 — Memory pack lives in the repository
Persistent project memory is stored under `docs/project-memory/` and versioned with Git.

## Decision 010 — Separate memory format from project state
Rules for writing memory live under `format/`; actual project state lives under `docs/project-memory/`.

## Decision 011 — AI handoff protocol
GPT acts as technical architect/reviewer. The user is the operator. Spark acts as implementer.

Loop:
`GPT → plan → USER → Spark → implementation → USER → GPT review → next step`

## Decision 012 — Evidence before migration
A model test should distinguish real LLM output from deterministic fallback where possible. A generic PASS is not enough evidence when fallback can produce the answer.

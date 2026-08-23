# Vaultify — Regression Record

## Baseline
- R1 extracted regression gate: `33 passed in 4.53s`.
- R1 closure structural/package/repository hygiene audit: PASS.
- Apple FY2025 Net Sales: `$416,161 million`.
- Tesla Q4 2025 Total Revenue: `$24,901 million`.

## LLM migration evidence
### Isolated model checks
- `openai/gpt-oss-120b`: PASS
- Returned model: `openai/gpt-oss-120b`
- `openai/gpt-oss-20b`: PASS
- Returned model: `openai/gpt-oss-20b`

These were isolated live model checks. They prove that the tested runtime received responses from those model IDs, but do not prove full Vaultify compatibility.

## Acceptance gate still required
For the selected production model, record each result as:
- `PASS — LLM-generated`
- `PASS — deterministic fallback`
- `FAIL`
- `BLOCKED`

Required scenarios:
1. Apple canonical query.
2. Tesla canonical query.
3. Ambiguous question requiring clarification.
4. Outside-corpus question requiring no-answer.
5. MCP `ask_documents`.
6. Tenant isolation / fail-closed behavior where applicable.

## Regression rule
Never call a test PASS merely because the final text looks correct if deterministic fallback could have generated it. Identify the execution path first when feasible.

## Historical evidence
Phase 3.8 / R1 included real OAuth + MCP acceptance with external Claude and grounded Apple evidence. R1 closure recorded no live Qdrant point modifications.

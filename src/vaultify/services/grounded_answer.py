"""Grounded answer generation extracted from Vaultify golden Cell 21E."""

import re

from vaultify.config import LLM_MODEL
from vaultify.services.evidence_verification import retrieve_and_verify_v1


def compact_answer_text(text):
    return re.sub(r"[^a-z0-9]+", "", str(text or "").lower())


def clean_currency_spacing(value):
    value = str(value or "").strip()
    return re.sub(r"([$€£])\s+", r"\1", value)


def format_verified_value(extracted_value):
    raw_value = clean_currency_spacing(extracted_value.get("value", ""))
    unit = extracted_value.get("unit", "document units")

    if unit == "USD millions":
        return f"{raw_value} million" if raw_value.startswith("$") else f"${raw_value} million"
    if unit == "USD":
        return raw_value if raw_value.startswith("$") else f"${raw_value}"
    if unit == "percent":
        return raw_value
    if unit == "billion":
        return raw_value if "b" in raw_value.lower() else f"{raw_value} billion"
    return raw_value


def build_verified_fact_packet(verification_result):
    facts = []

    for route in verification_result.get("route_verifications", []):
        best_evidence = route.get("best_evidence")
        if not best_evidence:
            continue

        extracted_value = best_evidence.get("extracted_value")
        if not extracted_value:
            continue

        metric = route.get("metric") or {}
        period = route.get("period") or {}
        source = best_evidence.get("source", {})

        facts.append(
            {
                "entity": route.get("entity"),
                "metric": metric.get("label", "requested metric"),
                "period": period.get("label", "requested period"),
                "raw_value": extracted_value.get("value"),
                "value_compact": extracted_value.get("value_compact"),
                "display_value": format_verified_value(extracted_value),
                "unit": extracted_value.get("unit"),
                "extraction_method": extracted_value.get("method"),
                "filename": source.get("filename"),
                "section": source.get("section"),
                "retrieval_rank": source.get("retrieval_rank"),
                "chunk_type": source.get("chunk_type"),
            }
        )

    return facts


def build_source_cards(facts):
    return [
        {
            "entity": fact["entity"],
            "filename": fact["filename"],
            "section": fact["section"],
            "metric": fact["metric"],
            "period": fact["period"],
            "value": fact["display_value"],
            "retrieval_rank": fact["retrieval_rank"],
        }
        for fact in facts
    ]


def build_deterministic_answer(verification_result, facts):
    status = verification_result["verification_status"]

    if status == "clarification_required":
        return verification_result.get("clarification") or (
            "Please specify the company and reporting period."
        )

    if status == "no_answer_candidate":
        return (
            "I could not identify relevant evidence for this question in the active "
            "organization's documents."
        )

    if status == "insufficient_evidence":
        verified_entities = [
            route["entity"]
            for route in verification_result.get("route_verifications", [])
            if route.get("verified")
        ]
        if verified_entities:
            return (
                "I found verified evidence for "
                + ", ".join(verified_entities)
                + ", but there was not enough verified evidence to answer the complete question."
            )
        return "I could not find sufficient verified evidence to answer this question."

    if status == "verified_single_entity":
        fact = facts[0]
        return (
            f"{fact['entity']}'s {fact['metric']} for {fact['period']} was "
            f"{fact['display_value']}. Source: {fact['filename']}, "
            f"section “{fact['section']}”."
        )

    if status == "verified_comparison":
        fact_sentences = [
            (
                f"{fact['entity']}'s {fact['metric']} for {fact['period']} was "
                f"{fact['display_value']}"
            )
            for fact in facts
        ]
        answer = "; ".join(fact_sentences) + "."
        warning = verification_result.get("period_scope_warning")
        if warning:
            answer += " " + warning
        answer += " Sources: " + "; ".join(
            f"{fact['filename']}, section “{fact['section']}”" for fact in facts
        ) + "."
        return answer

    return "The question could not be completed with the currently verified evidence."


def build_grounded_generation_prompt(verification_result, facts):
    fact_lines = []
    for fact_number, fact in enumerate(facts, start=1):
        fact_lines.append(
            "\n".join(
                [
                    f"FACT {fact_number}",
                    f"Entity: {fact['entity']}",
                    f"Metric: {fact['metric']}",
                    f"Period: {fact['period']}",
                    f"Verified value: {fact['display_value']}",
                    f"Unit classification: {fact['unit']}",
                    f"Source file: {fact['filename']}",
                    f"Source section: {fact['section']}",
                ]
            )
        )

    warning = verification_result.get("period_scope_warning") or "None"
    return (
        "USER QUESTION:\n"
        f"{verification_result['question']}\n\n"
        "VERIFIED FACTS:\n"
        + "\n\n".join(fact_lines)
        + "\n\nCOMPARISON WARNING:\n"
        f"{warning}\n\n"
        "Write the final answer using only the verified facts above."
    )


GROUNDED_ANSWER_SYSTEM_PROMPT = """
You are Vaultify's grounded document-answering engine.

Rules:
1. Use only the verified facts supplied by the application.
2. Preserve every verified numeric value exactly.
3. Do not invent, estimate, convert, calculate, or add numbers.
4. Do not change the supplied units.
5. Do not introduce information from general knowledge.
6. For a comparison, include every verified entity.
7. When a comparison warning is supplied, clearly explain it.
8. Mention the source file and section briefly.
9. Do not mention prompts, context numbers, retrieval ranks, or internal systems.
10. Keep the answer concise and professional.
""".strip()


def validate_generated_answer(answer, verification_result, facts):
    compact_answer = compact_answer_text(answer)
    missing_values = []

    for fact in facts:
        required_value = fact.get("value_compact")
        if required_value and required_value not in compact_answer:
            missing_values.append(
                {"entity": fact["entity"], "value": required_value}
            )

    warning_required = bool(verification_result.get("period_scope_warning"))
    warning_present = True

    if warning_required:
        lower_answer = str(answer).lower()
        has_comparison_phrase = any(
            phrase in lower_answer
            for phrase in [
                "not directly comparable",
                "not directly period-equivalent",
                "different reporting periods",
                "annual figure",
                "quarterly figure",
            ]
        )
        has_annual_and_quarter = "annual" in lower_answer and "quarter" in lower_answer
        warning_present = has_comparison_phrase or has_annual_and_quarter

    return {
        "passed": not missing_values and warning_present,
        "missing_values": missing_values,
        "warning_required": warning_required,
        "warning_present": warning_present,
    }


def generate_grounded_answer_v1(
    verification_result,
    *,
    groq_client=None,
    model=LLM_MODEL,
    use_llm=True,
):
    verification_status = verification_result["verification_status"]
    facts = build_verified_fact_packet(verification_result)
    sources = build_source_cards(facts)

    gated_statuses = {
        "clarification_required",
        "no_answer_candidate",
        "insufficient_evidence",
        "unsupported",
    }

    if verification_status in gated_statuses:
        answer = build_deterministic_answer(verification_result, facts)
        mapped_status = {
            "clarification_required": "clarification_required",
            "no_answer_candidate": "no_answer",
            "insufficient_evidence": "insufficient_evidence",
            "unsupported": "unsupported",
        }.get(verification_status, verification_status)
        return {
            "status": mapped_status,
            "answer": answer,
            "facts": facts,
            "sources": sources,
            "generation_method": "deterministic_gate",
            "llm_called": False,
            "generation_validation": None,
        }

    if not facts:
        return {
            "status": "insufficient_evidence",
            "answer": build_deterministic_answer(verification_result, facts),
            "facts": facts,
            "sources": sources,
            "generation_method": "deterministic_fallback",
            "llm_called": False,
            "generation_validation": None,
        }

    deterministic_answer = build_deterministic_answer(verification_result, facts)

    if not use_llm or groq_client is None:
        return {
            "status": "answered",
            "answer": deterministic_answer,
            "facts": facts,
            "sources": sources,
            "generation_method": "deterministic_verified",
            "llm_called": False,
            "generation_validation": validate_generated_answer(
                deterministic_answer,
                verification_result,
                facts,
            ),
        }

    user_prompt = build_grounded_generation_prompt(verification_result, facts)

    try:
        response = groq_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": GROUNDED_ANSWER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_tokens=350,
        )
        generated_answer = str(response.choices[0].message.content or "").strip()
        generation_validation = validate_generated_answer(
            generated_answer,
            verification_result,
            facts,
        )

        if not generated_answer or not generation_validation["passed"]:
            return {
                "status": "answered",
                "answer": deterministic_answer,
                "facts": facts,
                "sources": sources,
                "generation_method": "deterministic_fallback",
                "llm_called": True,
                "generation_validation": generation_validation,
            }

        return {
            "status": "answered",
            "answer": generated_answer,
            "facts": facts,
            "sources": sources,
            "generation_method": "groq_verified",
            "llm_called": True,
            "generation_validation": generation_validation,
        }
    except Exception as error:
        return {
            "status": "answered",
            "answer": deterministic_answer,
            "facts": facts,
            "sources": sources,
            "generation_method": "deterministic_fallback",
            "llm_called": True,
            "generation_error": str(error),
            "generation_validation": None,
        }


def answer_question_v2(
    tenant_id,
    question,
    *,
    runtime_tenant_id,
    entity_registry,
    retrieval_indexes,
    embedding_service,
    groq_client=None,
    model=LLM_MODEL,
    use_llm=True,
    top_k_per_entity=6,
    metric_expansions=None,
):
    """Run the Cell 21E pipeline with explicit runtime dependencies.

    ``tenant_id`` is the trusted tenant selected by the caller. The prepared
    runtime must declare the tenant it belongs to via ``runtime_tenant_id``;
    mismatches fail closed before retrieval.
    """
    tenant_id = str(tenant_id or "").strip()
    runtime_tenant_id = str(runtime_tenant_id or "").strip()

    if not tenant_id:
        raise ValueError("tenant_id is required.")
    if not runtime_tenant_id:
        raise ValueError("runtime_tenant_id is required.")
    if tenant_id != runtime_tenant_id:
        raise PermissionError(
            "The current orchestrator runtime belongs to a different tenant."
        )

    question = str(question or "").strip()
    if not question:
        raise ValueError("Question cannot be empty.")

    verification_result = retrieve_and_verify_v1(
        question,
        entity_registry,
        retrieval_indexes,
        embedding_service,
        top_k_per_entity=top_k_per_entity,
        metric_expansions=metric_expansions,
    )
    generation_result = generate_grounded_answer_v1(
        verification_result,
        groq_client=groq_client,
        model=model,
        use_llm=use_llm,
    )

    return {
        "tenant_id": tenant_id,
        "question": question,
        "status": generation_result["status"],
        "answer": generation_result["answer"],
        "sources": generation_result["sources"],
        "facts": generation_result["facts"],
        "generation_method": generation_result["generation_method"],
        "llm_called": generation_result["llm_called"],
        "generation_validation": generation_result.get("generation_validation"),
        "verification": verification_result,
    }

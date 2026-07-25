"""Approved Vaultify V2 answer service through golden Cell 21E.1."""

from vaultify.config import LLM_MODEL
from vaultify.services.evidence_verification import retrieve_and_verify_v1
from vaultify.services.grounded_answer import generate_grounded_answer_v1
from vaultify.services.unit_resolution import apply_contextual_units


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
    """Run the approved V2 pipeline with explicit tenant/runtime dependencies."""
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

    verification_result = apply_contextual_units(
        verification_result,
        retrieval_indexes,
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

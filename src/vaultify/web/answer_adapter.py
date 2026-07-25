"""Flask compatibility adapter for the clean Vaultify V2 answer service."""

from types import SimpleNamespace


WEB_SUPPORTED_ANSWER_STATUSES = {
    "answered",
    "clarification_required",
    "no_answer",
    "insufficient_evidence",
    "unsupported",
}


def normalize_retrieval_rank(retrieval_rank):
    try:
        retrieval_rank = int(retrieval_rank)
    except (TypeError, ValueError):
        return None
    return retrieval_rank if retrieval_rank >= 1 else None


def build_web_compatibility_score(retrieval_rank):
    normalized_rank = normalize_retrieval_rank(retrieval_rank)
    return 0.0 if normalized_rank is None else 1.0 / normalized_rank


def source_card_to_web_result(source_card):
    if not isinstance(source_card, dict):
        raise TypeError("Each verified source must be a dictionary.")

    retrieval_rank = normalize_retrieval_rank(source_card.get("retrieval_rank"))
    payload = {
        "filename": str(source_card.get("filename") or "Unknown file"),
        "section": str(source_card.get("section") or "Unknown section"),
        "entity": source_card.get("entity"),
        "metric": source_card.get("metric"),
        "period": source_card.get("period"),
        "value": source_card.get("value"),
        "retrieval_rank": retrieval_rank,
        "verified": True,
    }
    return SimpleNamespace(
        payload=payload,
        score=build_web_compatibility_score(retrieval_rank),
    )


def create_answer_question_v2_web_adapter(
    *,
    answer_service,
    runtime_provider,
    use_llm=True,
):
    """Create the legacy `/ask` contract around the clean V2 answer service.

    `runtime_provider(trusted_tenant_id)` must return the prepared dependencies for
    that tenant. The adapter never accepts a browser-supplied runtime tenant.
    """

    if not callable(answer_service):
        raise TypeError("answer_service must be callable.")
    if not callable(runtime_provider):
        raise TypeError("runtime_provider must be callable.")

    def adapter(question, tenant_id, **_ignored_arguments):
        cleaned_tenant_id = str(tenant_id or "").strip()
        cleaned_question = str(question or "").strip()

        if not cleaned_tenant_id:
            raise ValueError("tenant_id is required.")
        if not cleaned_question:
            raise ValueError("Question cannot be empty.")

        runtime = runtime_provider(cleaned_tenant_id)
        if not isinstance(runtime, dict):
            raise TypeError("runtime_provider must return a dictionary.")

        runtime_tenant_id = str(runtime.get("runtime_tenant_id") or "").strip()
        if runtime_tenant_id != cleaned_tenant_id:
            raise PermissionError(
                "The resolved V2 runtime belongs to a different tenant."
            )

        required_runtime_fields = {
            "entity_registry",
            "retrieval_indexes",
            "embedding_service",
        }
        missing_runtime_fields = required_runtime_fields - set(runtime)
        if missing_runtime_fields:
            raise RuntimeError(
                "The V2 runtime is incomplete. Missing fields: "
                + ", ".join(sorted(missing_runtime_fields))
            )

        orchestrator_result = answer_service(
            tenant_id=cleaned_tenant_id,
            question=cleaned_question,
            runtime_tenant_id=runtime_tenant_id,
            entity_registry=runtime["entity_registry"],
            retrieval_indexes=runtime["retrieval_indexes"],
            embedding_service=runtime["embedding_service"],
            groq_client=runtime.get("groq_client"),
            use_llm=use_llm,
            top_k_per_entity=runtime.get("top_k_per_entity", 6),
            metric_expansions=runtime.get("metric_expansions"),
        )

        if not isinstance(orchestrator_result, dict):
            raise TypeError("answer_question_v2 must return a dictionary.")

        required_result_fields = {
            "tenant_id",
            "question",
            "status",
            "answer",
            "sources",
        }
        missing_result_fields = required_result_fields - set(orchestrator_result)
        if missing_result_fields:
            raise RuntimeError(
                "answer_question_v2 returned an incomplete result. Missing fields: "
                + ", ".join(sorted(missing_result_fields))
            )

        returned_tenant_id = str(orchestrator_result.get("tenant_id") or "").strip()
        if returned_tenant_id != cleaned_tenant_id:
            raise PermissionError(
                "The orchestrator returned a different tenant_id than the trusted web tenant."
            )

        status = str(orchestrator_result.get("status") or "").strip()
        if status not in WEB_SUPPORTED_ANSWER_STATUSES:
            raise RuntimeError(f"Unsupported orchestrator status: {status!r}")

        answer = str(orchestrator_result.get("answer") or "").strip()
        if not answer:
            raise RuntimeError("The orchestrator returned an empty answer.")

        verified_source_cards = orchestrator_result.get("sources") or []
        if not isinstance(verified_source_cards, list):
            raise TypeError("The orchestrator sources field must be a list.")

        web_results = [
            source_card_to_web_result(source_card)
            for source_card in verified_source_cards
        ]

        return {
            "answer": answer,
            "results": web_results,
            "tenant_id": returned_tenant_id,
            "question": orchestrator_result["question"],
            "status": status,
            "sources": verified_source_cards,
            "facts": orchestrator_result.get("facts", []),
            "generation_method": orchestrator_result.get("generation_method"),
            "llm_called": orchestrator_result.get("llm_called"),
            "generation_validation": orchestrator_result.get("generation_validation"),
            "verification": orchestrator_result.get("verification"),
        }

    return adapter

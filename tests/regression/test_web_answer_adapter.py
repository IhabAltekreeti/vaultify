import pytest

from vaultify.web.answer_adapter import create_answer_question_v2_web_adapter


RUNTIME = {
    "runtime_tenant_id": "tenant_demo",
    "entity_registry": {"Acme": {"aliases": ["acme"]}},
    "retrieval_indexes": {"Acme": object()},
    "embedding_service": object(),
    "groq_client": object(),
}


def runtime_provider(tenant_id):
    assert tenant_id == "tenant_demo"
    return RUNTIME


def fake_answer_service(**kwargs):
    question = kwargs["question"]
    tenant_id = kwargs["tenant_id"]

    if question == "outside":
        return {
            "tenant_id": tenant_id,
            "question": question,
            "status": "no_answer",
            "answer": "No verified answer is available.",
            "sources": [],
            "facts": [],
            "generation_method": "deterministic_gate",
            "llm_called": False,
        }

    return {
        "tenant_id": tenant_id,
        "question": question,
        "status": "answered",
        "answer": "Acme revenue was $10 million.",
        "sources": [
            {
                "entity": "Acme",
                "filename": "acme_report.pdf",
                "section": "Revenue",
                "metric": "revenue",
                "period": "2026",
                "value": "$10 million",
                "retrieval_rank": 2,
            }
        ],
        "facts": [{"entity": "Acme"}],
        "generation_method": "deterministic_verified",
        "llm_called": False,
    }


def test_web_adapter_preserves_trusted_tenant_and_legacy_result_shape():
    adapter = create_answer_question_v2_web_adapter(
        answer_service=fake_answer_service,
        runtime_provider=runtime_provider,
        use_llm=False,
    )

    result = adapter(question="Acme revenue?", tenant_id="tenant_demo")

    assert result["tenant_id"] == "tenant_demo"
    assert result["status"] == "answered"
    assert result["answer"] == "Acme revenue was $10 million."
    assert len(result["results"]) == 1
    assert result["results"][0].payload["filename"] == "acme_report.pdf"
    assert result["results"][0].payload["verified"] is True
    assert result["results"][0].score == 0.5


def test_web_adapter_allows_zero_source_no_answer_contract():
    adapter = create_answer_question_v2_web_adapter(
        answer_service=fake_answer_service,
        runtime_provider=runtime_provider,
        use_llm=False,
    )

    result = adapter(question="outside", tenant_id="tenant_demo")

    assert result["status"] == "no_answer"
    assert result["results"] == []
    assert result["sources"] == []
    assert result["llm_called"] is False


def test_web_adapter_fails_closed_on_runtime_tenant_mismatch():
    def mismatched_runtime_provider(_tenant_id):
        return {**RUNTIME, "runtime_tenant_id": "different_tenant"}

    adapter = create_answer_question_v2_web_adapter(
        answer_service=fake_answer_service,
        runtime_provider=mismatched_runtime_provider,
    )

    with pytest.raises(PermissionError):
        adapter(question="Acme revenue?", tenant_id="tenant_demo")


def test_web_adapter_fails_closed_if_orchestrator_changes_tenant():
    def bad_answer_service(**kwargs):
        result = fake_answer_service(**kwargs)
        result["tenant_id"] = "different_tenant"
        return result

    adapter = create_answer_question_v2_web_adapter(
        answer_service=bad_answer_service,
        runtime_provider=runtime_provider,
    )

    with pytest.raises(PermissionError):
        adapter(question="Acme revenue?", tenant_id="tenant_demo")


def test_web_adapter_rejects_unsupported_status():
    def bad_status_service(**kwargs):
        result = fake_answer_service(**kwargs)
        result["status"] = "mystery_status"
        return result

    adapter = create_answer_question_v2_web_adapter(
        answer_service=bad_status_service,
        runtime_provider=runtime_provider,
    )

    with pytest.raises(RuntimeError, match="Unsupported orchestrator status"):
        adapter(question="Acme revenue?", tenant_id="tenant_demo")

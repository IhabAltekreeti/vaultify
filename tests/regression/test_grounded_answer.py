from types import SimpleNamespace

import pytest

import vaultify.services.grounded_answer as grounded_answer


def make_verified_route(entity, metric_label, period_label, value, value_compact, filename):
    return {
        "entity": entity,
        "metric": {"label": metric_label},
        "period": {"label": period_label},
        "verified": True,
        "best_evidence": {
            "extracted_value": {
                "value": value,
                "value_compact": value_compact,
                "unit": "USD millions",
                "method": "table_row_column",
            },
            "source": {
                "filename": filename,
                "section": "Financial Statements",
                "retrieval_rank": 1,
                "chunk_type": "table",
            },
        },
    }


def make_single_verification():
    return {
        "question": "What were Acme's total net sales in fiscal year 2025?",
        "verification_status": "verified_single_entity",
        "route_verifications": [
            make_verified_route(
                "Acme",
                "total net sales",
                "fiscal year 2025",
                "$416,161",
                "416161",
                "acme_2025.pdf",
            )
        ],
        "period_scope_warning": None,
        "clarification": None,
    }


def make_comparison_verification():
    return {
        "question": "Compare Acme fiscal 2025 sales with Beta Q4 2025 revenue.",
        "verification_status": "verified_comparison",
        "route_verifications": [
            make_verified_route(
                "Acme",
                "net sales",
                "fiscal year 2025",
                "$416,161",
                "416161",
                "acme_2025.pdf",
            ),
            make_verified_route(
                "Beta",
                "revenue",
                "Q4 2025",
                "$24,901",
                "24901",
                "beta_q4_2025.pdf",
            ),
        ],
        "period_scope_warning": (
            "The figures are not directly period-equivalent because one is annual and one is quarterly."
        ),
        "clarification": None,
    }


class FakeGroq:
    def __init__(self, text):
        self.calls = 0
        self.text = text
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self.create)
        )

    def create(self, **kwargs):
        self.calls += 1
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self.text)
                )
            ]
        )


def test_verified_answers_are_grounded_and_llm_output_is_validated():
    verification = make_single_verification()

    deterministic = grounded_answer.generate_grounded_answer_v1(
        verification,
        use_llm=False,
    )
    assert deterministic["status"] == "answered"
    assert deterministic["llm_called"] is False
    assert "416,161" in deterministic["answer"]
    assert deterministic["sources"][0]["entity"] == "Acme"

    valid_client = FakeGroq(
        "Acme's total net sales were $416,161 million. Source: acme_2025.pdf, Financial Statements."
    )
    generated = grounded_answer.generate_grounded_answer_v1(
        verification,
        groq_client=valid_client,
        use_llm=True,
    )
    assert generated["generation_method"] == "groq_verified"
    assert generated["llm_called"] is True
    assert generated["generation_validation"]["passed"] is True
    assert valid_client.calls == 1

    invalid_client = FakeGroq("Acme reported strong sales.")
    fallback = grounded_answer.generate_grounded_answer_v1(
        verification,
        groq_client=invalid_client,
        use_llm=True,
    )
    assert fallback["generation_method"] == "deterministic_fallback"
    assert "416,161" in fallback["answer"]
    assert fallback["generation_validation"]["passed"] is False


def test_comparison_and_early_gates_preserve_golden_behavior():
    comparison = grounded_answer.generate_grounded_answer_v1(
        make_comparison_verification(),
        use_llm=False,
    )
    assert comparison["status"] == "answered"
    assert "416,161" in comparison["answer"]
    assert "24,901" in comparison["answer"]
    assert "not directly period-equivalent" in comparison["answer"]
    assert {source["entity"] for source in comparison["sources"]} == {"Acme", "Beta"}

    client = FakeGroq("should not be called")

    clarification = grounded_answer.generate_grounded_answer_v1(
        {
            "question": "What was total revenue in 2025?",
            "verification_status": "clarification_required",
            "route_verifications": [],
            "clarification": "Which company do you mean?",
            "period_scope_warning": None,
        },
        groq_client=client,
        use_llm=True,
    )
    assert clarification["status"] == "clarification_required"
    assert clarification["llm_called"] is False

    outside = grounded_answer.generate_grounded_answer_v1(
        {
            "question": "Who wrote a novel?",
            "verification_status": "no_answer_candidate",
            "route_verifications": [],
            "clarification": None,
            "period_scope_warning": None,
        },
        groq_client=client,
        use_llm=True,
    )
    assert outside["status"] == "no_answer"
    assert outside["llm_called"] is False
    assert client.calls == 0


def test_answer_question_v2_fails_closed_on_runtime_tenant_mismatch(monkeypatch):
    verification = make_single_verification()

    monkeypatch.setattr(
        grounded_answer,
        "retrieve_and_verify_v1",
        lambda *args, **kwargs: verification,
    )

    with pytest.raises(PermissionError):
        grounded_answer.answer_question_v2(
            "tenant_a",
            verification["question"],
            runtime_tenant_id="tenant_b",
            entity_registry={},
            retrieval_indexes={},
            embedding_service=object(),
            use_llm=False,
        )

    result = grounded_answer.answer_question_v2(
        "tenant_a",
        verification["question"],
        runtime_tenant_id="tenant_a",
        entity_registry={},
        retrieval_indexes={},
        embedding_service=object(),
        use_llm=False,
    )
    assert result["tenant_id"] == "tenant_a"
    assert result["status"] == "answered"
    assert "416,161" in result["answer"]

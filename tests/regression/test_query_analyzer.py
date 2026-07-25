from vaultify.services.query_analyzer import analyze_query_v1


ENTITY_REGISTRY = {
    "Apple": {
        "aliases": ["apple", "apple inc", "aapl"],
        "filenames": ["apple_fy2025_10k.pdf"],
    },
    "Tesla": {
        "aliases": ["tesla", "tesla inc", "tsla"],
        "filenames": ["tesla_q4_2025_update.pdf"],
    },
}


def test_query_analyzer_golden_regression():
    apple = analyze_query_v1(
        "What were Apple's total net sales in fiscal year 2025?",
        ENTITY_REGISTRY,
    )
    assert apple["query_type"] == "single_entity"
    assert apple["entities"] == ["Apple"]
    assert apple["metrics"][0]["canonical"] == "total_net_sales"
    assert apple["periods"][0]["kind"] == "fiscal_year"
    assert apple["periods"][0]["year"] == 2025

    tesla = analyze_query_v1(
        "What was Tesla's total revenue in Q4 2025?",
        ENTITY_REGISTRY,
    )
    assert tesla["query_type"] == "single_entity"
    assert tesla["entities"] == ["Tesla"]
    assert tesla["metrics"][0]["canonical"] == "total_revenue"
    assert tesla["periods"][0]["kind"] == "quarter"
    assert tesla["periods"][0]["quarter"] == 4
    assert tesla["periods"][0]["year"] == 2025

    comparison = analyze_query_v1(
        "Compare Apple's fiscal 2025 net sales with Tesla's Q4 2025 revenue.",
        ENTITY_REGISTRY,
    )
    assert comparison["query_type"] == "comparison"
    assert comparison["entities"] == ["Apple", "Tesla"]
    assert [item["entity"] for item in comparison["subqueries"]] == [
        "Apple",
        "Tesla",
    ]
    assert comparison["period_scope_mismatch"] is True
    assert "not directly period-equivalent" in comparison["period_scope_warning"]

    ambiguous = analyze_query_v1(
        "What was the total revenue in 2025?",
        ENTITY_REGISTRY,
    )
    assert ambiguous["query_type"] == "ambiguous"
    assert ambiguous["entities"] == []
    assert ambiguous["needs_clarification"] is True
    assert "Apple or Tesla" in ambiguous["clarification_message"]

    outside = analyze_query_v1(
        "Who wrote Pride and Prejudice?",
        ENTITY_REGISTRY,
    )
    assert outside["query_type"] == "no_answer_candidate"
    assert outside["entities"] == []

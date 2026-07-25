from vaultify.services.evidence_verification import (
    verify_evidence_chunk_v1,
    verify_routed_question_v1,
)


APPLE_METRIC = {
    "canonical": "total_net_sales",
    "label": "total net sales",
    "quantitative": True,
}
APPLE_PERIOD = {
    "kind": "fiscal_year",
    "year": 2025,
    "quarter": None,
    "label": "fiscal year 2025",
}

TESLA_METRIC = {
    "canonical": "total_revenue",
    "label": "total revenue",
    "quantitative": True,
}
TESLA_PERIOD = {
    "kind": "quarter",
    "year": 2025,
    "quarter": 4,
    "label": "Q4 2025",
}


def make_result(*, entity, text, rank=1, filename="report.pdf", section="Financials"):
    return {
        "entity": entity,
        "rank": rank,
        "text": text,
        "filename": filename,
        "section": section,
        "chunk_type": "table",
        "point_id": f"{entity.lower()}-{rank}",
        "document_hash": f"{entity.lower()}-hash",
        "source_chunk_index": rank - 1,
        "hybrid_score": 0.03,
        "dense_rank": rank,
        "lexical_rank": rank,
    }


def make_route(entity, metric, period, result):
    return {
        "entity": entity,
        "metric": metric,
        "period": period,
        "retrieval_query": f"{entity} {period['label']} {metric['label']}",
        "results": [result],
    }


def test_table_row_column_value_extraction_matches_golden_behavior():
    apple_item = make_result(
        entity="Apple",
        filename="apple_fy2025_10k.pdf",
        section="Note 2 - Revenue",
        text=(
            "Section: Note 2 - Revenue | 2025 | 2024 | 2023 | "
            "Total net sales | $416,161 | $391,035 | $383,285 |"
        ),
    )
    apple = verify_evidence_chunk_v1(apple_item, APPLE_METRIC, APPLE_PERIOD)
    assert apple["verified"] is True
    assert apple["extracted_value"]["value_compact"] == "416161"
    assert apple["extracted_value"]["method"] == "table_row_column"

    tesla_item = make_result(
        entity="Tesla",
        filename="tesla_q4_2025_update.pdf",
        section="Unaudited",
        text=(
            "Dollars in millions | Q4-2025 | Q3-2025 | Q4-2024 | "
            "Total revenues | 24,901 | 28,095 | 25,707 |"
        ),
    )
    tesla = verify_evidence_chunk_v1(tesla_item, TESLA_METRIC, TESLA_PERIOD)
    assert tesla["verified"] is True
    assert tesla["extracted_value"]["value_compact"] == "24901"
    assert tesla["extracted_value"]["unit"] == "USD millions"
    assert tesla["extracted_value"]["method"] == "table_row_column"


def test_routed_verification_requires_every_comparison_side():
    apple_result = make_result(
        entity="Apple",
        filename="apple_fy2025_10k.pdf",
        text="2025 | 2024 | Total net sales | 416,161 | 391,035 |",
    )
    tesla_result = make_result(
        entity="Tesla",
        filename="tesla_q4_2025_update.pdf",
        text="Q4-2025 | Q3-2025 | Total revenues | 24,901 | 28,095 |",
    )

    routed = {
        "question": "Compare Apple and Tesla",
        "status": "comparison_retrieved",
        "clarification": None,
        "analysis": {
            "query_type": "comparison",
            "period_scope_warning": "annual vs quarterly",
        },
        "routes": [
            make_route("Apple", APPLE_METRIC, APPLE_PERIOD, apple_result),
            make_route("Tesla", TESLA_METRIC, TESLA_PERIOD, tesla_result),
        ],
    }

    verified = verify_routed_question_v1(routed)
    assert verified["verification_status"] == "verified_comparison"
    assert all(route["verified"] for route in verified["route_verifications"])

    broken_tesla = make_result(
        entity="Tesla",
        filename="tesla_q4_2025_update.pdf",
        text="Q4-2025 | Q3-2025 | Vehicle deliveries | 495,570 | 462,890 |",
    )
    routed["routes"][1] = make_route(
        "Tesla", TESLA_METRIC, TESLA_PERIOD, broken_tesla
    )

    incomplete = verify_routed_question_v1(routed)
    assert incomplete["verification_status"] == "insufficient_evidence"
    assert incomplete["route_verifications"][1]["verified"] is False


def test_non_retrieval_statuses_are_preserved_without_fabricating_evidence():
    clarification = verify_routed_question_v1(
        {
            "question": "What was total revenue in 2025?",
            "status": "clarification_required",
            "clarification": "Which company?",
            "analysis": {
                "query_type": "ambiguous",
                "period_scope_warning": None,
            },
            "routes": [],
        }
    )
    assert clarification["verification_status"] == "clarification_required"
    assert clarification["route_verifications"] == []

    outside = verify_routed_question_v1(
        {
            "question": "Who wrote Pride and Prejudice?",
            "status": "no_answer_candidate",
            "clarification": None,
            "analysis": {
                "query_type": "no_answer_candidate",
                "period_scope_warning": None,
            },
            "routes": [],
        }
    )
    assert outside["verification_status"] == "no_answer_candidate"
    assert outside["route_verifications"] == []

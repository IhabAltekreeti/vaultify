from vaultify.services.unit_resolution import (
    apply_contextual_units,
    resolve_contextual_financial_unit,
)


METRIC = {
    "canonical": "total_net_sales",
    "label": "total net sales",
}


def test_neighboring_unit_context_resolves_usd_millions():
    retrieval_indexes = {
        "Apple": {
            "chunks": [
                {
                    "point_id": "a0",
                    "filename": "apple.pdf",
                    "chunk_index": 10,
                    "section": "Revenue",
                    "text": "Apple Inc. Total net sales | $416,161 | $391,035",
                },
                {
                    "point_id": "a1",
                    "filename": "apple.pdf",
                    "chunk_index": 11,
                    "section": "Revenue",
                    "text": "In millions, except number of shares which are reflected in thousands.",
                },
            ]
        }
    }

    result = resolve_contextual_financial_unit(
        {
            "entity": "Apple",
            "point_id": "a0",
            "filename": "apple.pdf",
            "source_chunk_index": 10,
            "section": "Revenue",
            "text": "Apple Inc. Total net sales | $416,161 | $391,035",
        },
        METRIC,
        {
            "value": "$416,161",
            "value_compact": "416161",
            "unit": "USD",
            "method": "table_row_column",
        },
        retrieval_indexes,
    )

    assert result["unit"] == "USD millions"
    assert result["method"] == "weighted_source_context"
    assert result["scale_scores"]["millions"] > result["scale_scores"].get(
        "thousands", 0
    )


def test_existing_explicit_unit_is_preserved():
    result = resolve_contextual_financial_unit(
        {
            "entity": "Tesla",
            "filename": "tesla.pdf",
            "source_chunk_index": 1,
            "section": "Financial Statements",
            "text": "($ in millions) Total revenues | 24,901",
        },
        {"canonical": "total_revenue", "label": "total revenue"},
        {
            "value": "24,901",
            "value_compact": "24901",
            "unit": "USD millions",
            "method": "table_row_column",
        },
        {"Tesla": {"chunks": []}},
    )

    assert result["unit"] == "USD millions"
    assert result["method"] == "existing_explicit_unit"


def test_apply_contextual_units_updates_verified_best_evidence():
    evidence = {
        "verified": True,
        "extracted_value": {
            "value": "$416,161",
            "value_compact": "416161",
            "unit": "USD",
            "method": "table_row_column",
        },
        "source": {
            "entity": "Apple",
            "filename": "apple.pdf",
            "section": "Revenue",
            "chunk_type": "table",
            "point_id": "a0",
            "chunk_index": 10,
        },
        "text": "Apple Inc. Total net sales | $416,161 | $391,035",
    }
    verification = {
        "verification_status": "verified_single_entity",
        "route_verifications": [
            {
                "entity": "Apple",
                "metric": METRIC,
                "period": {
                    "kind": "fiscal_year",
                    "year": 2025,
                    "quarter": None,
                    "label": "fiscal year 2025",
                },
                "verified": True,
                "best_evidence": evidence,
                "best_candidate": evidence,
                "candidate_verifications": [evidence],
            }
        ],
    }
    retrieval_indexes = {
        "Apple": {
            "chunks": [
                {
                    "point_id": "a0",
                    "filename": "apple.pdf",
                    "chunk_index": 10,
                    "section": "Revenue",
                    "text": "Apple Inc. Total net sales | $416,161 | $391,035",
                },
                {
                    "point_id": "a1",
                    "filename": "apple.pdf",
                    "chunk_index": 11,
                    "section": "Revenue",
                    "text": "In millions",
                },
            ]
        }
    }

    resolved = apply_contextual_units(verification, retrieval_indexes)
    best = resolved["route_verifications"][0]["best_evidence"]

    assert best["extracted_value"]["unit"] == "USD millions"
    assert best["unit_resolution"]["method"] == "weighted_source_context"

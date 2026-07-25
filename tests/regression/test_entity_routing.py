import numpy as np

from vaultify.services.document_catalog import build_document_catalog
from vaultify.services.entity_routing import (
    build_routed_retrieval_query,
    prepare_entity_retrieval_indexes,
    retrieval_context_contains_groups,
    route_query_v1,
)


ENTITY_RULES = {
    "Apple": {
        "filename_terms": {"apple", "aapl"},
        "content_terms": {"apple inc"},
        "aliases": {"apple", "apple inc", "aapl"},
    },
    "Tesla": {
        "filename_terms": {"tesla", "tsla"},
        "content_terms": {"tesla inc"},
        "aliases": {"tesla", "tesla inc", "tsla"},
    },
}


class FakeEmbeddingService:
    def __init__(self):
        self.query_calls = 0

    @staticmethod
    def _vector(text):
        normalized = str(text or "").lower()
        vector = np.array(
            [
                1.0 if "sales" in normalized else 0.0,
                1.0 if "revenue" in normalized else 0.0,
                1.0 if "2025" in normalized else 0.0,
            ],
            dtype=np.float32,
        )
        norm = np.linalg.norm(vector)
        if norm == 0:
            return np.array([0.0, 0.0, 1.0], dtype=np.float32)
        return vector / norm

    def encode_documents(self, texts, *, batch_size=32, show_progress_bar=False):
        return np.vstack([self._vector(text) for text in texts])

    def encode_query(self, question):
        self.query_calls += 1
        return self._vector(question)


def make_chunk(point_id, filename, document_hash, chunk_index, text):
    return {
        "point_id": point_id,
        "tenant_id": "tenant_regression",
        "filename": filename,
        "document_hash": document_hash,
        "chunk_index": chunk_index,
        "chunk_type": "table",
        "section": "Financial Statements",
        "text": text,
        "payload": {},
    }


def test_aggregate_metric_expansion_preserves_golden_cell_21c1_patch():
    query = build_routed_retrieval_query(
        {
            "entity": "Apple",
            "metric": {
                "canonical": "net_sales",
                "label": "net sales",
            },
            "period": {
                "label": "fiscal year 2025",
            },
        }
    )

    assert query == "Apple fiscal year 2025 total net sales net sales"


def test_entity_routed_hybrid_retrieval_matches_golden_control_flow():
    chunks = [
        make_chunk(
            "a1",
            "apple_fy2025_10k.pdf",
            "apple_hash",
            0,
            "Apple Inc. fiscal 2025 total net sales were 416,161 million.",
        ),
        make_chunk(
            "a2",
            "apple_fy2025_10k.pdf",
            "apple_hash",
            1,
            "Apple Inc. services information for fiscal 2025.",
        ),
        make_chunk(
            "t1",
            "tesla_q4_2025_update.pdf",
            "tesla_hash",
            0,
            "Tesla Inc. Q4 2025 total revenue was 24,901 million.",
        ),
        make_chunk(
            "t2",
            "tesla_q4_2025_update.pdf",
            "tesla_hash",
            1,
            "Tesla Inc. vehicle deliveries in Q4 2025.",
        ),
    ]

    catalog, registry = build_document_catalog(
        chunks,
        "tenant_regression",
        entity_rules=ENTITY_RULES,
    )

    embeddings = FakeEmbeddingService()
    indexes = prepare_entity_retrieval_indexes(catalog, registry, embeddings)

    apple = route_query_v1(
        "What were Apple's total net sales in fiscal year 2025?",
        registry,
        indexes,
        embeddings,
        top_k_per_entity=2,
    )
    assert apple["status"] == "single_entity_retrieved"
    assert [route["entity"] for route in apple["routes"]] == ["Apple"]
    passed, _ = retrieval_context_contains_groups(
        apple["routes"][0]["results"],
        [["416,161", "416161"], ["total net sales"]],
    )
    assert passed

    tesla = route_query_v1(
        "What was Tesla's total revenue in Q4 2025?",
        registry,
        indexes,
        embeddings,
        top_k_per_entity=2,
    )
    assert tesla["status"] == "single_entity_retrieved"
    assert [route["entity"] for route in tesla["routes"]] == ["Tesla"]
    passed, _ = retrieval_context_contains_groups(
        tesla["routes"][0]["results"],
        [["24,901", "24901"], ["total revenue"]],
    )
    assert passed

    comparison = route_query_v1(
        "Compare Apple's fiscal 2025 net sales with Tesla's Q4 2025 revenue.",
        registry,
        indexes,
        embeddings,
        top_k_per_entity=2,
    )
    assert comparison["status"] == "comparison_retrieved"
    assert [route["entity"] for route in comparison["routes"]] == [
        "Apple",
        "Tesla",
    ]
    assert comparison["routes"][0]["retrieval_query"] == (
        "Apple fiscal year 2025 total net sales net sales"
    )
    assert comparison["routes"][1]["retrieval_query"] == (
        "Tesla Q4 2025 total revenue total revenues revenue revenues"
    )

    calls_before_non_retrieval = embeddings.query_calls

    ambiguous = route_query_v1(
        "What was the total revenue in 2025?",
        registry,
        indexes,
        embeddings,
    )
    assert ambiguous["status"] == "clarification_required"
    assert ambiguous["routes"] == []

    outside = route_query_v1(
        "Who wrote Pride and Prejudice?",
        registry,
        indexes,
        embeddings,
    )
    assert outside["status"] == "no_answer_candidate"
    assert outside["routes"] == []

    assert embeddings.query_calls == calls_before_non_retrieval

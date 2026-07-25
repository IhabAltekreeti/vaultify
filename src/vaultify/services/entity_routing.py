"""Entity-routed hybrid retrieval extracted from Vaultify golden Cell 21C."""

import re

from vaultify.services.query_analyzer import analyze_query_v1
from vaultify.services.retrieval import prepare_hybrid_index, retrieve_hybrid


DEFAULT_METRIC_EXPANSIONS = {
    "total_net_sales": [
        "total net sales",
        "net sales",
    ],
    "services_net_sales": [
        "services net sales",
        "services",
    ],
    "iphone_net_sales": [
        "iPhone net sales",
        "iPhone",
    ],
    "net_sales": [
        "net sales",
    ],
    "total_revenue": [
        "total revenue",
        "total revenues",
        "revenue",
        "revenues",
    ],
    "revenue": [
        "revenue",
        "revenues",
        "total revenue",
        "total revenues",
    ],
    "automotive_revenue": [
        "automotive revenue",
        "automotive revenues",
        "total automotive revenues",
    ],
    "energy_storage_revenue": [
        "energy generation and storage revenue",
        "energy generation and storage revenues",
        "energy storage revenue",
    ],
    "gaap_operating_income": [
        "GAAP operating income",
        "operating income",
    ],
    "operating_income": [
        "operating income",
    ],
}


def build_routed_retrieval_query(subquery, *, metric_expansions=None):
    """Build the concise entity-specific retrieval query used by golden Cell 21C."""
    metric_expansions = metric_expansions or DEFAULT_METRIC_EXPANSIONS

    entity = str(subquery.get("entity", "")).strip()
    metric = subquery.get("metric")
    period = subquery.get("period")
    query_parts = []

    if entity:
        query_parts.append(entity)

    if period:
        period_label = str(period.get("label", "")).strip()
        if period_label:
            query_parts.append(period_label)

    if metric:
        metric_name = metric.get("canonical")
        expansions = metric_expansions.get(
            metric_name,
            [metric.get("label", "")],
        )
        query_parts.extend(expansion for expansion in expansions if expansion)
    else:
        segment = str(subquery.get("segment", "")).strip()
        segment = re.sub(
            r"^\s*compare\s+",
            "",
            segment,
            flags=re.IGNORECASE,
        )
        segment = re.sub(
            r"\s+with\s*$",
            "",
            segment,
            flags=re.IGNORECASE,
        )
        if segment:
            query_parts.append(segment)

    return re.sub(r"\s+", " ", " ".join(query_parts)).strip()


def collect_entity_chunks(entity, document_catalog, entity_registry):
    """Collect unique normalized chunks belonging to one registered entity."""
    registry_entry = entity_registry.get(entity)
    if not registry_entry:
        raise KeyError(f"Unknown entity: {entity}")

    entity_chunks = []
    seen_point_ids = set()
    observed_tenants = set()

    for document_key in registry_entry.get("document_keys", []):
        document = document_catalog.get(document_key)
        if not document:
            continue

        document_tenant = document.get("tenant_id")
        if document_tenant:
            observed_tenants.add(document_tenant)

        for chunk in document.get("chunks", []):
            chunk_tenant = chunk.get("tenant_id")
            if chunk_tenant:
                observed_tenants.add(chunk_tenant)

            point_id = str(chunk.get("point_id", ""))
            if point_id and point_id in seen_point_ids:
                continue
            if point_id:
                seen_point_ids.add(point_id)

            entity_chunks.append(
                {
                    "point_id": point_id,
                    "tenant_id": chunk_tenant or document_tenant,
                    "filename": chunk.get("filename", document.get("filename", "unknown_document")),
                    "document_hash": chunk.get("document_hash", document.get("document_hash")),
                    "chunk_index": chunk.get("chunk_index"),
                    "chunk_type": chunk.get("chunk_type", "unknown"),
                    "section": chunk.get("section", "Unknown section"),
                    "text": chunk["text"],
                    "entity": entity,
                }
            )

    if len(observed_tenants) > 1:
        raise RuntimeError(
            f"Entity {entity!r} spans multiple tenants: {sorted(observed_tenants)}"
        )

    entity_chunks.sort(
        key=lambda chunk: (
            chunk["filename"],
            chunk["chunk_index"] if isinstance(chunk["chunk_index"], int) else 0,
            chunk["point_id"],
        )
    )

    if not entity_chunks:
        raise RuntimeError(f"No usable chunks were found for entity {entity!r}.")

    return entity_chunks


def prepare_entity_retrieval_indexes(
    document_catalog,
    entity_registry,
    embedding_service,
    *,
    batch_size=64,
    show_progress_bar=False,
):
    """Build one in-memory Dense + BM25 index per entity."""
    indexes = {}

    for entity in sorted(entity_registry):
        chunks = collect_entity_chunks(entity, document_catalog, entity_registry)
        prepared = prepare_hybrid_index(
            chunks,
            embedding_service,
            batch_size=batch_size,
            show_progress_bar=show_progress_bar,
        )
        prepared["entity"] = entity
        indexes[entity] = prepared

    return indexes


def retrieve_for_entity_v1(
    entity,
    retrieval_query,
    retrieval_indexes,
    embedding_service,
    *,
    top_k=6,
):
    """Run hybrid retrieval only against the selected entity's documents."""
    retrieval_index = retrieval_indexes.get(entity)
    if not retrieval_index:
        raise KeyError(f"No retrieval index exists for entity {entity!r}.")

    retrieved = retrieve_hybrid(
        retrieval_index,
        retrieval_query,
        embedding_service,
        top_k=top_k,
    )

    enriched_results = []
    for item in retrieved:
        enriched_item = dict(item)
        enriched_item["entity"] = entity
        enriched_results.append(enriched_item)

    return enriched_results


def route_query_v1(
    question,
    entity_registry,
    retrieval_indexes,
    embedding_service,
    *,
    top_k_per_entity=6,
    metric_expansions=None,
):
    """Analyze a question and execute the golden entity-routing strategy."""
    analysis = analyze_query_v1(question, entity_registry)
    query_type = analysis["query_type"]

    routed_result = {
        "question": question,
        "analysis": analysis,
        "status": None,
        "routes": [],
        "clarification": None,
    }

    if query_type == "ambiguous":
        routed_result["status"] = "clarification_required"
        routed_result["clarification"] = analysis["clarification_message"]
        return routed_result

    if query_type == "no_answer_candidate":
        routed_result["status"] = "no_answer_candidate"
        return routed_result

    if query_type == "corpus_general":
        routed_result["status"] = "corpus_general_pending"
        return routed_result

    if query_type not in {"single_entity", "comparison"}:
        routed_result["status"] = "unsupported_query_type"
        return routed_result

    for subquery in analysis["subqueries"]:
        entity = subquery["entity"]
        retrieval_query = build_routed_retrieval_query(
            subquery,
            metric_expansions=metric_expansions,
        )
        retrieved = retrieve_for_entity_v1(
            entity,
            retrieval_query,
            retrieval_indexes,
            embedding_service,
            top_k=top_k_per_entity,
        )
        routed_result["routes"].append(
            {
                "entity": entity,
                "metric": subquery.get("metric"),
                "period": subquery.get("period"),
                "retrieval_query": retrieval_query,
                "results": retrieved,
            }
        )

    routed_result["status"] = (
        "comparison_retrieved"
        if query_type == "comparison"
        else "single_entity_retrieved"
    )
    return routed_result


def normalize_retrieval_evidence(text):
    normalized = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    compact = re.sub(r"[^a-z0-9]+", "", normalized)
    return normalized, compact


def retrieval_context_contains_groups(retrieved_results, expected_groups):
    """Return whether every expected evidence group appears in routed results."""
    combined_context = " ".join(item["text"] for item in retrieved_results)
    normalized_context, compact_context = normalize_retrieval_evidence(combined_context)

    group_results = []
    for alternatives in expected_groups:
        matched = None
        for alternative in alternatives:
            normalized_alternative, compact_alternative = normalize_retrieval_evidence(
                alternative
            )
            if normalized_alternative in normalized_context or (
                compact_alternative and compact_alternative in compact_context
            ):
                matched = alternative
                break
        group_results.append({"alternatives": alternatives, "matched": matched})

    return all(group["matched"] is not None for group in group_results), group_results

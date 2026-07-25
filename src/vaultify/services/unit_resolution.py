"""Context-aware financial unit resolution from golden Cell 21E.1."""

from collections import defaultdict
from copy import deepcopy
import html
import re

from vaultify.services.evidence_verification import metric_aliases_for_verification


MONETARY_METRIC_NAMES = {
    "total_net_sales",
    "services_net_sales",
    "iphone_net_sales",
    "net_sales",
    "total_revenue",
    "revenue",
    "automotive_revenue",
    "energy_storage_revenue",
    "gaap_operating_income",
    "operating_income",
}


UNIT_SCALE_PATTERNS = {
    "billions": [
        r"\bin\s+billions?\b",
        r"\bdollars?\s+in\s+billions?\b",
        r"\busd\s+in\s+billions?\b",
        r"\$\s+in\s+billions?\b",
    ],
    "millions": [
        r"\bin\s+millions?\b",
        r"\bdollars?\s+in\s+millions?\b",
        r"\busd\s+in\s+millions?\b",
        r"\$\s+in\s+millions?\b",
    ],
    "thousands": [
        r"\bin\s+thousands?\b",
        r"\bdollars?\s+in\s+thousands?\b",
        r"\busd\s+in\s+thousands?\b",
        r"\$\s+in\s+thousands?\b",
    ],
}


PRECISE_UNITS = {
    "USD millions",
    "USD billions",
    "USD thousands",
    "percent",
    "billion",
}


def is_monetary_metric(metric):
    if not metric:
        return False

    canonical_name = metric.get("canonical", "")
    if canonical_name in MONETARY_METRIC_NAMES:
        return True

    metric_label = str(metric.get("label", "")).lower()
    return any(
        term in metric_label
        for term in [
            "sales",
            "revenue",
            "income",
            "expense",
            "cost",
            "cash",
            "assets",
            "liabilities",
        ]
    )


def normalize_unit_context_text(text):
    normalized = html.unescape(str(text or "")).lower()
    normalized = (
        normalized.replace("’", "'").replace("–", "-").replace("—", "-")
    )
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def detect_explicit_unit_scale(text):
    normalized_text = normalize_unit_context_text(text)

    for scale, patterns in UNIT_SCALE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, normalized_text):
                return scale

    return None


def unit_context_chunk_key(chunk):
    point_id = str(chunk.get("point_id", "")).strip()
    if point_id:
        return ("point", point_id)

    return (
        "chunk",
        chunk.get("filename"),
        chunk.get("chunk_index"),
        chunk.get("section"),
    )


def collect_unit_context_candidates(
    item,
    metric,
    retrieval_indexes,
    *,
    metric_expansions=None,
):
    """Collect weighted source context around one verified evidence chunk."""
    entity = item.get("entity")
    retrieval_index = retrieval_indexes.get(entity)
    if not retrieval_index:
        return []

    source_chunks = retrieval_index.get("chunks", [])
    filename = item.get("filename")
    section = item.get("section")
    source_chunk_index = item.get("source_chunk_index")

    metric_aliases = metric_aliases_for_verification(
        metric,
        metric_expansions=metric_expansions,
    )

    candidates = {}

    def add_candidate(chunk, weight, reason):
        key = unit_context_chunk_key(chunk)
        previous = candidates.get(key)
        if previous is None or weight > previous["weight"]:
            candidates[key] = {
                "chunk": chunk,
                "weight": float(weight),
                "reason": reason,
            }

    add_candidate(
        {
            "point_id": item.get("point_id"),
            "filename": filename,
            "chunk_index": source_chunk_index,
            "section": section,
            "text": item.get("text", ""),
        },
        weight=10,
        reason="current_chunk",
    )

    same_document_chunks = [
        chunk for chunk in source_chunks if chunk.get("filename") == filename
    ]

    for chunk in same_document_chunks:
        chunk_index = chunk.get("chunk_index")
        chunk_text = chunk.get("text", "")
        chunk_section = chunk.get("section")

        if isinstance(source_chunk_index, int) and isinstance(chunk_index, int):
            distance = abs(chunk_index - source_chunk_index)
            if 0 < distance <= 4:
                add_candidate(
                    chunk,
                    weight=9 - distance,
                    reason=f"neighbor_distance_{distance}",
                )

        if section and chunk_section == section:
            add_candidate(chunk, weight=6, reason="same_section")

        normalized_chunk_text = normalize_unit_context_text(chunk_text)
        has_metric_alias = any(
            alias in normalized_chunk_text for alias in metric_aliases
        )
        explicit_scale = detect_explicit_unit_scale(chunk_text)

        if has_metric_alias and explicit_scale:
            add_candidate(chunk, weight=7, reason="metric_and_unit")
        elif explicit_scale:
            add_candidate(chunk, weight=2, reason="document_unit_signal")

    return list(candidates.values())


def resolve_contextual_financial_unit(
    item,
    metric,
    extracted_value,
    retrieval_indexes,
    *,
    metric_expansions=None,
):
    """Resolve a financial scale from the verified chunk and related source context."""
    base_unit = str(extracted_value.get("unit", "document units"))
    raw_value = str(extracted_value.get("value", ""))

    if base_unit in PRECISE_UNITS:
        return {
            "unit": base_unit,
            "method": "existing_explicit_unit",
            "scale_scores": {},
            "support": [],
        }

    if not is_monetary_metric(metric):
        return {
            "unit": base_unit,
            "method": "non_monetary_metric",
            "scale_scores": {},
            "support": [],
        }

    context_candidates = collect_unit_context_candidates(
        item,
        metric,
        retrieval_indexes,
        metric_expansions=metric_expansions,
    )

    scale_scores = defaultdict(float)
    supporting_context = []

    for candidate in context_candidates:
        chunk = candidate["chunk"]
        scale = detect_explicit_unit_scale(chunk.get("text", ""))
        if not scale:
            continue

        weight = candidate["weight"]
        scale_scores[scale] += weight
        supporting_context.append(
            {
                "scale": scale,
                "weight": weight,
                "reason": candidate["reason"],
                "filename": chunk.get("filename"),
                "section": chunk.get("section"),
                "chunk_index": chunk.get("chunk_index"),
            }
        )

    if not scale_scores:
        return {
            "unit": base_unit,
            "method": "no_contextual_scale_found",
            "scale_scores": {},
            "support": [],
        }

    resolved_scale = max(scale_scores, key=scale_scores.get)
    combined_context = " ".join(
        candidate["chunk"].get("text", "") for candidate in context_candidates
    )
    normalized_context = normalize_unit_context_text(combined_context)

    is_usd = (
        "$" in raw_value
        or base_unit == "USD"
        or "$" in combined_context
        or "usd" in normalized_context
        or "u.s. dollar" in normalized_context
        or "dollars in" in normalized_context
    )

    resolved_unit = f"USD {resolved_scale}" if is_usd else resolved_scale

    return {
        "unit": resolved_unit,
        "method": "weighted_source_context",
        "scale_scores": dict(scale_scores),
        "support": sorted(
            supporting_context,
            key=lambda entry: entry["weight"],
            reverse=True,
        )[:8],
    }


def _evidence_item(route, evidence):
    source = evidence.get("source", {})
    return {
        "entity": route.get("entity"),
        "filename": source.get("filename"),
        "section": source.get("section"),
        "source_chunk_index": source.get("chunk_index"),
        "point_id": source.get("point_id"),
        "chunk_type": source.get("chunk_type"),
        "text": evidence.get("text", ""),
    }


def apply_contextual_units(
    verification_result,
    retrieval_indexes,
    *,
    metric_expansions=None,
):
    """Return a copy of a verification result enriched with contextual units."""
    resolved = deepcopy(verification_result)

    for route in resolved.get("route_verifications", []):
        metric = route.get("metric")

        for evidence in route.get("candidate_verifications", []):
            extracted_value = evidence.get("extracted_value")
            if not extracted_value:
                continue

            resolution = resolve_contextual_financial_unit(
                _evidence_item(route, evidence),
                metric,
                extracted_value,
                retrieval_indexes,
                metric_expansions=metric_expansions,
            )
            extracted_value["unit"] = resolution["unit"]
            evidence["unit_resolution"] = resolution

    return resolved

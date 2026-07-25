"""Structured evidence verification extracted from Vaultify golden Cell 21D."""

import html
import re

from vaultify.services.entity_routing import DEFAULT_METRIC_EXPANSIONS, route_query_v1


def normalize_evidence_phrase(text):
    normalized = html.unescape(str(text or "")).lower()
    normalized = (
        normalized.replace("’", "'").replace("–", "-").replace("—", "-")
    )
    normalized = re.sub(r"[^a-z0-9.%$€£&+\-]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def compact_evidence_phrase(text):
    return re.sub(r"[^a-z0-9]+", "", normalize_evidence_phrase(text))


def normalize_table_cell(text):
    normalized = html.unescape(str(text or ""))
    return re.sub(r"\s+", " ", normalized).strip()


def metric_aliases_for_verification(metric, *, metric_expansions=None):
    if not metric:
        return []

    metric_expansions = metric_expansions or DEFAULT_METRIC_EXPANSIONS
    canonical_name = metric.get("canonical")
    aliases = list(metric_expansions.get(canonical_name, []))

    label = metric.get("label")
    if label:
        aliases.append(label)

    unique_aliases = []
    seen_aliases = set()

    for alias in aliases:
        normalized_alias = normalize_evidence_phrase(alias)
        if normalized_alias and normalized_alias not in seen_aliases:
            seen_aliases.add(normalized_alias)
            unique_aliases.append(normalized_alias)

    unique_aliases.sort(key=len, reverse=True)
    return unique_aliases


def find_metric_alias_in_text(text, metric, *, metric_expansions=None):
    normalized_text = normalize_evidence_phrase(text)

    for alias in metric_aliases_for_verification(
        metric,
        metric_expansions=metric_expansions,
    ):
        pattern = r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])"
        if re.search(pattern, normalized_text):
            return alias

    return None


def canonicalize_period_cell(cell):
    normalized_cell = normalize_evidence_phrase(cell)

    quarter_match = re.fullmatch(
        r"q([1-4])[\s\-]*((?:19|20)\d{2})",
        normalized_cell,
    )
    if quarter_match:
        return {
            "kind": "quarter",
            "quarter": int(quarter_match.group(1)),
            "year": int(quarter_match.group(2)),
            "label": f"Q{quarter_match.group(1)} {quarter_match.group(2)}",
        }

    year_match = re.fullmatch(r"((?:19|20)\d{2})", normalized_cell)
    if year_match:
        return {
            "kind": "year",
            "quarter": None,
            "year": int(year_match.group(1)),
            "label": year_match.group(1),
        }

    return None


def period_matches_header(requested_period, header_period):
    if not requested_period:
        return True
    if not header_period:
        return False

    if requested_period.get("year") != header_period.get("year"):
        return False

    requested_quarter = requested_period.get("quarter")
    if requested_quarter is not None:
        return requested_quarter == header_period.get("quarter")

    return True


def period_signals_present(text, period):
    if not period:
        return True

    normalized_text = normalize_evidence_phrase(text)
    year = period.get("year")
    quarter = period.get("quarter")

    if year is None:
        return True
    if str(year) not in normalized_text:
        return False
    if quarter is not None:
        return bool(re.search(rf"\bq\s*{quarter}\b", normalized_text))

    return True


NUMERIC_CELL_PATTERN = re.compile(
    r"""
    ^\s*\(?[\$€£]?\s*-?\d[\d,]*(?:\.\d+)?\s*
    (?:%|[kmb]|thousand|million|billion)?\s*\)?\s*$
    """,
    flags=re.IGNORECASE | re.VERBOSE,
)

NUMERIC_SEARCH_PATTERN = re.compile(
    r"""
    (?:[\$€£]\s*)?\(?-?\d[\d,]*(?:\.\d+)?\s*
    (?:%|[kmb]|thousand|million|billion)?\)?
    """,
    flags=re.IGNORECASE | re.VERBOSE,
)


def is_numeric_table_cell(cell):
    cleaned_cell = normalize_table_cell(cell)
    if not cleaned_cell:
        return False
    if cleaned_cell in {"-", "—", "–"}:
        return True
    return bool(NUMERIC_CELL_PATTERN.fullmatch(cleaned_cell))


def compact_numeric_value(value):
    return re.sub(
        r"[^0-9a-z.%\-]+",
        "",
        normalize_evidence_phrase(value),
    )


def infer_value_unit(chunk_text, raw_value):
    normalized_text = normalize_evidence_phrase(chunk_text)
    normalized_value = normalize_evidence_phrase(raw_value)

    if "%" in normalized_value:
        return "percent"
    if "billion" in normalized_value:
        return "billion"
    if re.search(r"\d(?:\.\d+)?\s*b\b", normalized_value):
        return "billion"
    if (
        "in millions" in normalized_text
        or "dollars in millions" in normalized_text
        or "$ in millions" in normalized_text
    ):
        return "USD millions"
    if "$" in str(raw_value):
        return "USD"
    return "document units"


def metric_cell_candidates(cells, metric, *, metric_expansions=None):
    aliases = metric_aliases_for_verification(
        metric,
        metric_expansions=metric_expansions,
    )
    candidates = []

    for cell_index, cell in enumerate(cells):
        normalized_cell = normalize_evidence_phrase(cell)
        if not normalized_cell:
            continue

        for alias_priority, alias in enumerate(aliases):
            if normalized_cell == alias:
                match_strength = 3
            elif normalized_cell.startswith(alias):
                match_strength = 2
            elif re.search(
                r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])",
                normalized_cell,
            ):
                match_strength = 1
            else:
                continue

            candidates.append(
                {
                    "cell_index": cell_index,
                    "cell": cell,
                    "alias": alias,
                    "alias_priority": alias_priority,
                    "match_strength": match_strength,
                }
            )

    candidates.sort(
        key=lambda candidate: (
            candidate["alias_priority"],
            -candidate["match_strength"],
            candidate["cell_index"],
        )
    )
    return candidates


def extract_period_value_from_table(
    text,
    metric,
    period,
    *,
    metric_expansions=None,
):
    """Extract the requested metric-row / period-column intersection."""
    if "|" not in str(text):
        return None

    cells = [normalize_table_cell(cell) for cell in str(text).split("|")]
    metric_candidates = metric_cell_candidates(
        cells,
        metric,
        metric_expansions=metric_expansions,
    )

    for metric_candidate in metric_candidates:
        metric_cell_index = metric_candidate["cell_index"]
        header_periods = []

        for header_index in range(0, metric_cell_index):
            parsed_period = canonicalize_period_cell(cells[header_index])
            if parsed_period:
                header_periods.append(
                    {"cell_index": header_index, "period": parsed_period}
                )

        unique_header_periods = []
        seen_period_keys = set()

        for header_entry in header_periods:
            period_key = (
                header_entry["period"]["year"],
                header_entry["period"]["quarter"],
            )
            if period_key in seen_period_keys:
                continue
            seen_period_keys.add(period_key)
            unique_header_periods.append(header_entry)

        if not unique_header_periods:
            continue

        requested_column_ordinal = next(
            (
                column_ordinal
                for column_ordinal, header_entry in enumerate(unique_header_periods)
                if period_matches_header(period, header_entry["period"])
            ),
            None,
        )
        if requested_column_ordinal is None:
            continue

        row_numeric_values = []
        for value_cell in cells[metric_cell_index + 1 :]:
            if is_numeric_table_cell(value_cell):
                row_numeric_values.append(value_cell)
                if len(row_numeric_values) >= len(unique_header_periods):
                    break
            elif row_numeric_values:
                break

        if requested_column_ordinal >= len(row_numeric_values):
            continue

        raw_value = row_numeric_values[requested_column_ordinal]
        return {
            "value": raw_value,
            "value_compact": compact_numeric_value(raw_value),
            "unit": infer_value_unit(text, raw_value),
            "metric_alias": metric_candidate["alias"],
            "period_label": unique_header_periods[requested_column_ordinal][
                "period"
            ]["label"],
            "method": "table_row_column",
        }

    return None


def extract_value_from_text_window(
    text,
    metric,
    period,
    *,
    metric_expansions=None,
):
    normalized_text = normalize_evidence_phrase(text)
    aliases = metric_aliases_for_verification(
        metric,
        metric_expansions=metric_expansions,
    )
    requested_year = period.get("year") if period else None

    for alias in aliases:
        alias_match = re.search(
            r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])",
            normalized_text,
        )
        if not alias_match:
            continue

        window_start = max(0, alias_match.start() - 80)
        window_end = min(len(normalized_text), alias_match.end() + 220)
        evidence_window = normalized_text[window_start:window_end]

        for numeric_match in NUMERIC_SEARCH_PATTERN.finditer(evidence_window):
            raw_value = numeric_match.group(0).strip()
            compact_value = compact_numeric_value(raw_value)
            if requested_year is not None and compact_value == str(requested_year):
                continue

            return {
                "value": raw_value,
                "value_compact": compact_value,
                "unit": infer_value_unit(text, raw_value),
                "metric_alias": alias,
                "period_label": period.get("label") if period else None,
                "method": "text_window",
            }

    return None


def verify_evidence_chunk_v1(
    item,
    metric,
    period,
    *,
    metric_expansions=None,
):
    text = item.get("text", "")
    matched_metric_alias = find_metric_alias_in_text(
        text,
        metric,
        metric_expansions=metric_expansions,
    )
    period_present = period_signals_present(text, period)

    extracted_value = extract_period_value_from_table(
        text=text,
        metric=metric,
        period=period,
        metric_expansions=metric_expansions,
    )
    if extracted_value is None:
        extracted_value = extract_value_from_text_window(
            text=text,
            metric=metric,
            period=period,
            metric_expansions=metric_expansions,
        )

    metric_present = matched_metric_alias is not None
    numeric_present = extracted_value is not None
    table_bonus = 1 if item.get("chunk_type") == "table" else 0
    extraction_bonus = (
        4
        if extracted_value and extracted_value["method"] == "table_row_column"
        else (2 if extracted_value else 0)
    )
    verification_score = (
        extraction_bonus
        + (2 if metric_present else 0)
        + (2 if period_present else 0)
        + table_bonus
        + max(0.0, 1.0 - (item.get("rank", 99) - 1) * 0.10)
    )
    verified = metric_present and period_present and numeric_present

    return {
        "verified": verified,
        "verification_score": float(verification_score),
        "metric_present": metric_present,
        "matched_metric_alias": matched_metric_alias,
        "period_present": period_present,
        "numeric_present": numeric_present,
        "extracted_value": extracted_value,
        "source": {
            "entity": item.get("entity"),
            "filename": item.get("filename"),
            "document_hash": item.get("document_hash"),
            "section": item.get("section"),
            "chunk_type": item.get("chunk_type"),
            "point_id": item.get("point_id"),
            "chunk_index": item.get("source_chunk_index"),
            "retrieval_rank": item.get("rank"),
            "hybrid_score": item.get("hybrid_score"),
            "dense_rank": item.get("dense_rank"),
            "bm25_rank": item.get("lexical_rank"),
        },
        "text": text,
    }


def verify_route_evidence_v1(route, *, metric_expansions=None):
    candidate_verifications = [
        verify_evidence_chunk_v1(
            result,
            route.get("metric"),
            route.get("period"),
            metric_expansions=metric_expansions,
        )
        for result in route.get("results", [])
    ]
    candidate_verifications.sort(
        key=lambda candidate: (
            candidate["verified"],
            candidate["verification_score"],
        ),
        reverse=True,
    )

    best_candidate = candidate_verifications[0] if candidate_verifications else None
    route_verified = bool(best_candidate and best_candidate["verified"])

    return {
        "entity": route.get("entity"),
        "metric": route.get("metric"),
        "period": route.get("period"),
        "retrieval_query": route.get("retrieval_query"),
        "verified": route_verified,
        "best_evidence": best_candidate if route_verified else None,
        "best_candidate": best_candidate,
        "candidate_verifications": candidate_verifications,
    }


def verify_routed_question_v1(routed_result, *, metric_expansions=None):
    query_type = routed_result["analysis"]["query_type"]
    result = {
        "question": routed_result["question"],
        "analysis": routed_result["analysis"],
        "routing_status": routed_result["status"],
        "verification_status": None,
        "route_verifications": [],
        "clarification": routed_result.get("clarification"),
        "period_scope_warning": routed_result["analysis"].get(
            "period_scope_warning"
        ),
    }

    if routed_result["status"] == "clarification_required":
        result["verification_status"] = "clarification_required"
        return result

    if routed_result["status"] == "no_answer_candidate":
        result["verification_status"] = "no_answer_candidate"
        return result

    if query_type not in {"single_entity", "comparison"}:
        result["verification_status"] = "unsupported"
        return result

    route_verifications = [
        verify_route_evidence_v1(
            route,
            metric_expansions=metric_expansions,
        )
        for route in routed_result["routes"]
    ]
    result["route_verifications"] = route_verifications

    all_routes_verified = bool(route_verifications) and all(
        route["verified"] for route in route_verifications
    )

    if all_routes_verified:
        result["verification_status"] = (
            "verified_comparison"
            if query_type == "comparison"
            else "verified_single_entity"
        )
    else:
        result["verification_status"] = "insufficient_evidence"

    return result


def retrieve_and_verify_v1(
    question,
    entity_registry,
    retrieval_indexes,
    embedding_service,
    *,
    top_k_per_entity=6,
    metric_expansions=None,
):
    routed_result = route_query_v1(
        question,
        entity_registry,
        retrieval_indexes,
        embedding_service,
        top_k_per_entity=top_k_per_entity,
        metric_expansions=metric_expansions,
    )
    return verify_routed_question_v1(
        routed_result,
        metric_expansions=metric_expansions,
    )

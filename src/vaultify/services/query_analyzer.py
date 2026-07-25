"""Deterministic query analysis extracted from Vaultify golden Cell 21B."""

from copy import deepcopy
import re


COMPARISON_PATTERNS = [
    r"\bcompare\b",
    r"\bcomparison\b",
    r"\bversus\b",
    r"\bvs\.?\b",
    r"\bcompared\s+with\b",
    r"\bcompared\s+to\b",
    r"\bdifference\s+between\b",
    r"\bhow\s+does\b.*\bcompare\b",
]


METRIC_RULES = [
    {
        "canonical": "total_net_sales",
        "label": "total net sales",
        "patterns": [
            r"\btotal\s+net\s+sales\b",
            r"\bnet\s+sales\s+total\b",
        ],
        "quantitative": True,
    },
    {
        "canonical": "services_net_sales",
        "label": "services net sales",
        "patterns": [
            r"\bservices?\s+net\s+sales\b",
            r"\bnet\s+sales\s+from\s+services\b",
        ],
        "quantitative": True,
    },
    {
        "canonical": "iphone_net_sales",
        "label": "iPhone net sales",
        "patterns": [
            r"\biphone\s+net\s+sales\b",
            r"\bnet\s+sales\s+from\s+iphone\b",
        ],
        "quantitative": True,
    },
    {
        "canonical": "automotive_revenue",
        "label": "automotive revenue",
        "patterns": [
            r"\bautomotive\s+revenues?\b",
            r"\btotal\s+automotive\s+revenues?\b",
        ],
        "quantitative": True,
    },
    {
        "canonical": "energy_storage_revenue",
        "label": "energy generation and storage revenue",
        "patterns": [
            r"\benergy\s+generation\s+(?:and|&)\s+storage\s+revenues?\b",
            r"\benergy\s+storage\s+revenues?\b",
        ],
        "quantitative": True,
    },
    {
        "canonical": "gaap_operating_income",
        "label": "GAAP operating income",
        "patterns": [r"\bgaap\s+operating\s+income\b"],
        "quantitative": True,
    },
    {
        "canonical": "operating_income",
        "label": "operating income",
        "patterns": [r"\boperating\s+income\b"],
        "quantitative": True,
    },
    {
        "canonical": "total_revenue",
        "label": "total revenue",
        "patterns": [r"\btotal\s+revenues?\b"],
        "quantitative": True,
    },
    {
        "canonical": "net_sales",
        "label": "net sales",
        "patterns": [r"\bnet\s+sales\b"],
        "quantitative": True,
    },
    {
        "canonical": "revenue",
        "label": "revenue",
        "patterns": [r"\brevenues?\b"],
        "quantitative": True,
    },
]


DOCUMENT_SCOPE_PATTERNS = [
    r"\baccording\s+to\s+the\s+documents?\b",
    r"\bin\s+the\s+documents?\b",
    r"\bin\s+the\s+reports?\b",
    r"\bin\s+the\s+files?\b",
    r"\bsummarize\b",
    r"\bdocuments?\s+say\b",
    r"\breports?\s+say\b",
    r"\bacross\s+the\s+documents?\b",
]


def normalize_query_text(text):
    normalized = str(text or "")
    normalized = (
        normalized
        .replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
    )
    normalized = normalized.lower()
    normalized = re.sub(
        r"\bfy\s*[- ]?(\d{4})\b",
        r"fiscal year \1",
        normalized,
    )
    normalized = re.sub(
        r"\bfiscal\s+(\d{4})\b",
        r"fiscal year \1",
        normalized,
    )
    normalized = re.sub(
        r"\bq\s*([1-4])\s*[- ]?(\d{4})\b",
        r"q\1 \2",
        normalized,
    )
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def build_entity_alias_index(entity_registry):
    alias_records = []

    for entity, metadata in entity_registry.items():
        aliases = set(metadata.get("aliases", []))
        aliases.add(entity.lower())

        for alias in aliases:
            normalized_alias = normalize_query_text(alias)
            if not normalized_alias:
                continue
            alias_records.append(
                {
                    "entity": entity,
                    "alias": normalized_alias,
                }
            )

    alias_records.sort(
        key=lambda item: len(item["alias"]),
        reverse=True,
    )
    return alias_records


def detect_entity_mentions(normalized_question, entity_alias_index):
    mentions = []
    occupied_ranges = []

    for alias_record in entity_alias_index:
        entity = alias_record["entity"]
        alias = alias_record["alias"]
        alias_pattern = (
            r"(?<![a-z0-9])"
            + re.escape(alias)
            + r"(?:'s)?"
            + r"(?![a-z0-9])"
        )

        for match in re.finditer(alias_pattern, normalized_question):
            start, end = match.span()
            overlaps_existing = any(
                start < occupied_end and end > occupied_start
                for occupied_start, occupied_end in occupied_ranges
            )
            if overlaps_existing:
                continue

            mentions.append(
                {
                    "entity": entity,
                    "alias": alias,
                    "start": start,
                    "end": end,
                    "matched_text": match.group(0),
                }
            )
            occupied_ranges.append((start, end))

    mentions.sort(key=lambda item: (item["start"], item["end"]))
    return mentions


def detect_metrics(text):
    normalized_text = normalize_query_text(text)
    detected_metrics = []
    occupied_spans = []

    for rule in METRIC_RULES:
        for pattern in rule["patterns"]:
            match = re.search(pattern, normalized_text)
            if not match:
                continue

            start, end = match.span()
            overlaps_existing = any(
                start < existing_end and end > existing_start
                for existing_start, existing_end in occupied_spans
            )
            if overlaps_existing:
                continue

            detected_metrics.append(
                {
                    "canonical": rule["canonical"],
                    "label": rule["label"],
                    "quantitative": rule["quantitative"],
                    "matched_text": match.group(0),
                    "start": start,
                    "end": end,
                }
            )
            occupied_spans.append((start, end))
            break

    detected_metrics.sort(key=lambda item: (item["start"], item["end"]))
    return detected_metrics


def detect_periods(text):
    normalized_text = normalize_query_text(text)
    periods = []
    occupied_spans = []

    period_patterns = [
        {
            "kind": "quarter",
            "pattern": r"\bq([1-4])\s+((?:19|20)\d{2})\b",
        },
        {
            "kind": "fiscal_year",
            "pattern": r"\bfiscal\s+year\s+((?:19|20)\d{2})\b",
        },
        {
            "kind": "calendar_year",
            "pattern": r"\bcalendar\s+year\s+((?:19|20)\d{2})\b",
        },
        {
            "kind": "year_unspecified",
            "pattern": r"\b((?:19|20)\d{2})\b",
        },
    ]

    for period_rule in period_patterns:
        for match in re.finditer(period_rule["pattern"], normalized_text):
            start, end = match.span()
            overlaps_existing = any(
                start < existing_end and end > existing_start
                for existing_start, existing_end in occupied_spans
            )
            if overlaps_existing:
                continue

            kind = period_rule["kind"]
            if kind == "quarter":
                quarter = int(match.group(1))
                year = int(match.group(2))
                label = f"Q{quarter} {year}"
            else:
                quarter = None
                year = int(match.group(1))
                if kind == "fiscal_year":
                    label = f"fiscal year {year}"
                elif kind == "calendar_year":
                    label = f"calendar year {year}"
                else:
                    label = str(year)

            periods.append(
                {
                    "kind": kind,
                    "year": year,
                    "quarter": quarter,
                    "label": label,
                    "matched_text": match.group(0),
                    "start": start,
                    "end": end,
                }
            )
            occupied_spans.append((start, end))

    periods.sort(key=lambda item: (item["start"], item["end"]))
    return periods


def has_comparison_intent(normalized_question):
    return any(
        re.search(pattern, normalized_question)
        for pattern in COMPARISON_PATTERNS
    )


def has_document_scope_intent(normalized_question):
    return any(
        re.search(pattern, normalized_question)
        for pattern in DOCUMENT_SCOPE_PATTERNS
    )


def build_entity_segments(normalized_question, entity_mentions):
    if not entity_mentions:
        return []

    unique_mentions = []
    seen_entities = set()

    for mention in entity_mentions:
        if mention["entity"] in seen_entities:
            continue
        seen_entities.add(mention["entity"])
        unique_mentions.append(mention)

    segments = []
    for mention_index, mention in enumerate(unique_mentions):
        segment_start = 0 if mention_index == 0 else mention["start"]
        if mention_index + 1 < len(unique_mentions):
            segment_end = unique_mentions[mention_index + 1]["start"]
        else:
            segment_end = len(normalized_question)

        segment_text = normalized_question[segment_start:segment_end].strip(
            " ,.;:-"
        )
        segments.append(
            {
                "entity": mention["entity"],
                "segment": segment_text,
            }
        )

    return segments


def build_clarification_message(
    entity_registry,
    entities,
    metrics,
    periods,
    reason,
):
    entity_list = sorted(entity_registry.keys())
    entity_text = " or ".join(entity_list)
    metric_label = (
        metrics[0]["label"] if metrics else "the requested information"
    )

    if reason == "missing_entity":
        return (
            f"Which company do you mean: {entity_text}? Please also specify "
            f"the reporting period for {metric_label}."
        )

    if reason == "multiple_entities_without_comparison":
        return (
            "Your question refers to multiple companies. "
            "Should I compare them, or answer for only one company?"
        )

    if reason == "unspecified_period_scope":
        return (
            "Please specify whether you mean a fiscal year, calendar year, "
            "or a particular quarter."
        )

    return "Please specify the company, metric, and reporting period."


def analyze_query_v1(question, entity_registry):
    """Return the canonical deterministic query-analysis plan."""
    original_question = str(question or "").strip()
    if not original_question:
        raise ValueError("Question cannot be empty.")
    if not entity_registry:
        raise ValueError("Entity registry cannot be empty.")

    normalized_question = normalize_query_text(original_question)
    entity_alias_index = build_entity_alias_index(entity_registry)
    entity_mentions = detect_entity_mentions(
        normalized_question,
        entity_alias_index,
    )

    entities = []
    for mention in entity_mentions:
        if mention["entity"] not in entities:
            entities.append(mention["entity"])

    metrics = detect_metrics(normalized_question)
    periods = detect_periods(normalized_question)
    comparison_intent = has_comparison_intent(normalized_question)
    document_scope_intent = has_document_scope_intent(normalized_question)
    corpus_entities = sorted(entity_registry.keys())

    query_type = None
    needs_clarification = False
    clarification_reason = None
    clarification_message = None
    subqueries = []

    if comparison_intent and len(entities) >= 2:
        query_type = "comparison"
        entity_segments = build_entity_segments(
            normalized_question,
            entity_mentions,
        )

        for segment_entry in entity_segments:
            segment_metrics = detect_metrics(segment_entry["segment"])
            segment_periods = detect_periods(segment_entry["segment"])
            subqueries.append(
                {
                    "entity": segment_entry["entity"],
                    "metric": (
                        deepcopy(segment_metrics[0])
                        if segment_metrics
                        else None
                    ),
                    "period": (
                        deepcopy(segment_periods[0])
                        if segment_periods
                        else None
                    ),
                    "segment": segment_entry["segment"],
                    "retrieval_query": segment_entry["segment"],
                }
            )

    elif len(entities) >= 2:
        query_type = "ambiguous"
        needs_clarification = True
        clarification_reason = "multiple_entities_without_comparison"
        clarification_message = build_clarification_message(
            entity_registry,
            entities,
            metrics,
            periods,
            clarification_reason,
        )

    elif len(entities) == 1:
        query_type = "single_entity"
        subqueries.append(
            {
                "entity": entities[0],
                "metric": deepcopy(metrics[0]) if metrics else None,
                "period": deepcopy(periods[0]) if periods else None,
                "segment": normalized_question,
                "retrieval_query": normalized_question,
            }
        )

    elif len(corpus_entities) > 1 and (metrics or periods):
        query_type = "ambiguous"
        needs_clarification = True
        clarification_reason = "missing_entity"
        clarification_message = build_clarification_message(
            entity_registry,
            entities,
            metrics,
            periods,
            clarification_reason,
        )

    elif document_scope_intent:
        query_type = "corpus_general"

    else:
        query_type = "no_answer_candidate"

    period_scope_mismatch = False
    period_scope_warning = None

    if query_type == "comparison":
        comparison_periods = [
            subquery["period"]
            for subquery in subqueries
            if subquery["period"] is not None
        ]
        period_kinds = {period["kind"] for period in comparison_periods}

        if "quarter" in period_kinds and (
            "fiscal_year" in period_kinds
            or "calendar_year" in period_kinds
        ):
            period_scope_mismatch = True
            period_scope_warning = (
                "The comparison mixes an annual figure with a quarterly "
                "figure, so the values are not directly period-equivalent."
            )

    return {
        "original_question": original_question,
        "normalized_question": normalized_question,
        "query_type": query_type,
        "entities": entities,
        "entity_mentions": entity_mentions,
        "metrics": metrics,
        "periods": periods,
        "comparison_intent": comparison_intent,
        "document_scope_intent": document_scope_intent,
        "needs_clarification": needs_clarification,
        "clarification_reason": clarification_reason,
        "clarification_message": clarification_message,
        "subqueries": subqueries,
        "period_scope_mismatch": period_scope_mismatch,
        "period_scope_warning": period_scope_warning,
        "available_corpus_entities": corpus_entities,
    }

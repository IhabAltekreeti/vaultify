"""Read-only tenant-scoped and hybrid retrieval services for Vaultify."""

from collections import Counter, defaultdict
import html
import math
import re

import numpy as np
from qdrant_client.models import FieldCondition, Filter, MatchValue

from vaultify.config import COLLECTION_NAME, TENANT_ID_FIELD


HYBRID_STOPWORDS = {
    "a", "an", "and", "are", "as", "at",
    "be", "been", "by", "for", "from",
    "had", "has", "have", "how", "in",
    "is", "it", "its", "of", "on", "or",
    "s", "that", "the", "their", "this",
    "to", "was", "were", "what", "which",
    "who", "with",
}

QUANTITATIVE_TERMS = {
    "assets",
    "capacity",
    "cash",
    "cost",
    "costs",
    "earnings",
    "expense",
    "expenses",
    "income",
    "liabilities",
    "margin",
    "margins",
    "percent",
    "percentage",
    "revenue",
    "revenues",
    "sales",
    "total",
}


def first_payload_value(payload, candidate_keys, default=None):
    for key in candidate_keys:
        value = payload.get(key)
        if value is not None and value != "":
            return value
    return default


def payload_text(payload):
    return str(
        first_payload_value(
            payload,
            ["text", "content", "page_content", "chunk_text"],
            "",
        )
    ).strip()


def payload_filename(payload):
    return str(
        first_payload_value(
            payload,
            ["filename", "file_name", "document_name", "source"],
            "unknown_document",
        )
    ).strip()


def payload_document_hash(payload):
    value = first_payload_value(
        payload,
        ["document_hash", "file_hash", "sha256", "document_id"],
        None,
    )
    return None if value is None else str(value).strip()


def payload_section(payload):
    return str(
        first_payload_value(
            payload,
            ["section", "section_name", "heading", "title"],
            "Unknown section",
        )
    ).strip()


def payload_chunk_type(payload):
    return str(
        first_payload_value(
            payload,
            ["chunk_type", "type", "content_type"],
            "unknown",
        )
    ).strip().lower()


def payload_chunk_index(payload, fallback_index):
    value = first_payload_value(
        payload,
        ["chunk_index", "index", "chunk_id"],
        fallback_index,
    )
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback_index


def load_tenant_points(
    client,
    tenant_id,
    *,
    collection_name=COLLECTION_NAME,
    tenant_field=TENANT_ID_FIELD,
    batch_size=256,
):
    """Read every Qdrant point belonging to exactly one tenant."""
    tenant_filter = Filter(
        must=[
            FieldCondition(
                key=tenant_field,
                match=MatchValue(value=tenant_id),
            )
        ]
    )

    points = []
    next_offset = None

    while True:
        batch, next_offset = client.scroll(
            collection_name=collection_name,
            scroll_filter=tenant_filter,
            limit=batch_size,
            offset=next_offset,
            with_payload=True,
            with_vectors=False,
        )
        points.extend(batch)

        if next_offset is None:
            break

    return points


def normalize_tenant_points(points, tenant_id):
    """Convert Qdrant point payloads into stable Vaultify chunk records."""
    chunks = []

    for fallback_index, point in enumerate(points):
        payload = point.payload or {}
        text = payload_text(payload)
        if not text:
            continue

        chunks.append(
            {
                "point_id": str(point.id),
                "tenant_id": tenant_id,
                "filename": payload_filename(payload),
                "document_hash": payload_document_hash(payload),
                "chunk_index": payload_chunk_index(payload, fallback_index),
                "chunk_type": payload_chunk_type(payload),
                "section": payload_section(payload),
                "text": text,
                "payload": payload,
            }
        )

    return chunks


def load_tenant_chunks(
    client,
    tenant_id,
    *,
    collection_name=COLLECTION_NAME,
    tenant_field=TENANT_ID_FIELD,
    batch_size=256,
):
    """Load and normalize all usable chunks for exactly one tenant."""
    points = load_tenant_points(
        client,
        tenant_id,
        collection_name=collection_name,
        tenant_field=tenant_field,
        batch_size=batch_size,
    )

    chunks = normalize_tenant_points(points, tenant_id)

    if not chunks:
        raise RuntimeError(
            f"No usable Qdrant chunks were found for tenant {tenant_id!r}."
        )

    return chunks


def hybrid_tokenize(text):
    """Normalize text into lexical tokens while preserving years and values."""
    normalized = html.unescape(str(text or "")).lower()
    normalized = re.sub(r"(?<=\d),(?=\d)", "", normalized)
    tokens = re.findall(r"[a-z0-9]+", normalized)
    return [token for token in tokens if token not in HYBRID_STOPWORDS]


def build_bm25_index(chunks):
    """Build the canonical lightweight in-memory BM25 index."""
    document_tokens = [hybrid_tokenize(chunk["text"]) for chunk in chunks]
    term_frequencies = [Counter(tokens) for tokens in document_tokens]
    document_lengths = np.array(
        [len(tokens) for tokens in document_tokens],
        dtype=np.float32,
    )
    average_document_length = (
        float(document_lengths.mean()) if len(document_lengths) else 0.0
    )

    postings = defaultdict(list)
    for document_index, frequencies in enumerate(term_frequencies):
        for term, frequency in frequencies.items():
            postings[term].append((document_index, frequency))

    document_frequency = {
        term: len(entries)
        for term, entries in postings.items()
    }

    return {
        "document_tokens": document_tokens,
        "document_lengths": document_lengths,
        "average_document_length": average_document_length,
        "postings": dict(postings),
        "document_frequency": document_frequency,
        "document_count": len(chunks),
    }


def calculate_bm25_scores(index, question, k1=1.5, b=0.75):
    """Calculate canonical BM25 lexical relevance scores."""
    query_tokens = hybrid_tokenize(question)
    query_term_counts = Counter(query_tokens)
    scores = np.zeros(index["document_count"], dtype=np.float32)
    average_length = max(index["average_document_length"], 1.0)

    for term, query_frequency in query_term_counts.items():
        postings = index["postings"].get(term, [])
        document_frequency = index["document_frequency"].get(term, 0)

        if document_frequency == 0:
            continue

        inverse_document_frequency = math.log(
            1.0
            + (
                (index["document_count"] - document_frequency + 0.5)
                / (document_frequency + 0.5)
            )
        )

        for document_index, term_frequency in postings:
            document_length = index["document_lengths"][document_index]
            denominator = (
                term_frequency
                + k1
                * (
                    1.0
                    - b
                    + b * document_length / average_length
                )
            )
            score = (
                inverse_document_frequency
                * (term_frequency * (k1 + 1.0))
                / denominator
            )
            scores[document_index] += score * query_frequency

    return scores


def create_rank_array(scores):
    """Convert scores into one-based ranks."""
    order = np.argsort(scores)[::-1]
    ranks = np.empty(len(scores), dtype=np.int32)
    ranks[order] = np.arange(1, len(scores) + 1)
    return ranks


def build_query_phrases(query_tokens):
    """Create meaningful query bigrams and trigrams."""
    phrases = []
    for phrase_size in (3, 2):
        for start_index in range(0, len(query_tokens) - phrase_size + 1):
            phrases.append(
                " ".join(query_tokens[start_index:start_index + phrase_size])
            )
    return phrases


def prepare_hybrid_index(
    chunks,
    embedding_service,
    *,
    batch_size=64,
    show_progress_bar=False,
):
    """Prepare normalized dense embeddings and BM25 data for a chunk set."""
    if not chunks:
        raise ValueError("Hybrid retrieval requires at least one chunk.")

    embeddings = embedding_service.encode_documents(
        [chunk["text"] for chunk in chunks],
        batch_size=batch_size,
        show_progress_bar=show_progress_bar,
    )

    if len(embeddings) != len(chunks):
        raise RuntimeError("Embedding count does not match chunk count.")

    return {
        "chunks": list(chunks),
        "embeddings": embeddings,
        "bm25_index": build_bm25_index(chunks),
    }


def retrieve_hybrid(
    result,
    question,
    embedding_service,
    *,
    top_k=6,
    rrf_constant=60,
):
    """Run the canonical Dense + BM25 + RRF hybrid retrieval algorithm."""
    cleaned_question = str(question or "").strip()
    if not cleaned_question:
        raise ValueError("The retrieval question cannot be empty.")
    if top_k <= 0:
        raise ValueError("top_k must be greater than zero.")

    chunks = result["chunks"]
    if "bm25_index" not in result:
        result["bm25_index"] = build_bm25_index(chunks)

    query_embedding = embedding_service.encode_query(cleaned_question)
    dense_scores = result["embeddings"] @ query_embedding
    lexical_scores = calculate_bm25_scores(
        result["bm25_index"],
        cleaned_question,
    )

    dense_ranks = create_rank_array(dense_scores)
    lexical_ranks = create_rank_array(lexical_scores)
    query_tokens = hybrid_tokenize(cleaned_question)
    unique_query_tokens = set(query_tokens)
    query_phrases = build_query_phrases(query_tokens)
    query_years = {
        token
        for token in query_tokens
        if re.fullmatch(r"(?:19|20)\d{2}", token)
    }
    is_quantitative_query = bool(unique_query_tokens & QUANTITATIVE_TERMS)

    hybrid_scores = np.zeros(len(chunks), dtype=np.float32)
    feature_details = []

    for chunk_index, chunk in enumerate(chunks):
        document_tokens = result["bm25_index"]["document_tokens"][chunk_index]
        chunk_tokens = set(document_tokens)
        chunk_normalized = " ".join(document_tokens)

        reciprocal_rank_score = (
            1.0 / (rrf_constant + dense_ranks[chunk_index])
            + 1.0 / (rrf_constant + lexical_ranks[chunk_index])
        )

        lexical_coverage = (
            len(unique_query_tokens & chunk_tokens) / len(unique_query_tokens)
            if unique_query_tokens
            else 0.0
        )
        phrase_hits = sum(phrase in chunk_normalized for phrase in query_phrases)
        phrase_bonus = min(phrase_hits, 2) * 0.004
        year_bonus = (
            0.004
            if query_years and query_years.issubset(chunk_tokens)
            else 0.0
        )
        table_bonus = (
            0.002
            if is_quantitative_query and chunk.get("chunk_type") == "table"
            else 0.0
        )
        coverage_bonus = lexical_coverage * 0.010

        hybrid_scores[chunk_index] = (
            reciprocal_rank_score
            + coverage_bonus
            + phrase_bonus
            + year_bonus
            + table_bonus
        )

        feature_details.append(
            {
                "dense_rank": int(dense_ranks[chunk_index]),
                "lexical_rank": int(lexical_ranks[chunk_index]),
                "dense_score": float(dense_scores[chunk_index]),
                "lexical_score": float(lexical_scores[chunk_index]),
                "coverage": float(lexical_coverage),
                "phrase_hits": int(phrase_hits),
                "year_bonus": year_bonus,
                "table_bonus": table_bonus,
            }
        )

    top_indexes = np.argsort(hybrid_scores)[::-1][:top_k]
    results = []

    for rank, chunk_index in enumerate(top_indexes, start=1):
        chunk_index = int(chunk_index)
        chunk = chunks[chunk_index]
        features = feature_details[chunk_index]
        results.append(
            {
                "rank": rank,
                "chunk_index": chunk_index,
                "hybrid_score": float(hybrid_scores[chunk_index]),
                "dense_rank": features["dense_rank"],
                "lexical_rank": features["lexical_rank"],
                "dense_score": features["dense_score"],
                "lexical_score": features["lexical_score"],
                "coverage": features["coverage"],
                "text": chunk["text"],
                "section": chunk.get("section", "Unknown section"),
                "chunk_type": chunk.get("chunk_type", "unknown"),
                "point_id": chunk.get("point_id"),
                "tenant_id": chunk.get("tenant_id"),
                "filename": chunk.get("filename", "unknown_document"),
                "document_hash": chunk.get("document_hash"),
                "source_chunk_index": chunk.get("chunk_index"),
            }
        )

    return results

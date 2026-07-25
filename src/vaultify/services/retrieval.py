"""Read-only tenant-scoped retrieval foundation for Vaultify."""

from qdrant_client.models import FieldCondition, Filter, MatchValue

from vaultify.config import COLLECTION_NAME, TENANT_ID_FIELD


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

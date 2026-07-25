from vaultify.services.document_catalog import build_document_catalog


DEMO_ENTITY_RULES = {
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


def make_chunk(
    *,
    point_id,
    tenant_id,
    filename,
    document_hash,
    chunk_index,
    chunk_type,
    section,
    text,
):
    return {
        "point_id": point_id,
        "tenant_id": tenant_id,
        "filename": filename,
        "document_hash": document_hash,
        "chunk_index": chunk_index,
        "chunk_type": chunk_type,
        "section": section,
        "text": text,
        "payload": {},
    }


def test_document_catalog_and_registry_match_golden_shape():
    tenant_id = "tenant_regression"
    chunks = [
        make_chunk(
            point_id="a2",
            tenant_id=tenant_id,
            filename="apple_fy2025_10k.pdf",
            document_hash="apple_hash",
            chunk_index=2,
            chunk_type="table",
            section="Note 2 - Revenue",
            text="Apple Inc. fiscal 2025 total net sales 416,161.",
        ),
        make_chunk(
            point_id="a1",
            tenant_id=tenant_id,
            filename="apple_fy2025_10k.pdf",
            document_hash="apple_hash",
            chunk_index=1,
            chunk_type="text",
            section="Note 2 - Revenue",
            text="Apple Inc. reported fiscal 2025 results.",
        ),
        make_chunk(
            point_id="t1",
            tenant_id=tenant_id,
            filename="tesla_q4_2025_update.pdf",
            document_hash="tesla_hash",
            chunk_index=0,
            chunk_type="table",
            section="Financial Statements",
            text="Tesla Inc. Q4 2025 total revenue 24,901.",
        ),
    ]

    catalog, registry = build_document_catalog(
        chunks,
        tenant_id,
        entity_rules=DEMO_ENTITY_RULES,
    )

    assert set(catalog) == {"apple_hash", "tesla_hash"}
    assert catalog["apple_hash"]["chunk_count"] == 2
    assert catalog["apple_hash"]["chunk_types"] == {"text": 1, "table": 1}
    assert catalog["apple_hash"]["entities"] == ["Apple"]
    assert catalog["apple_hash"]["chunks"][0]["chunk_index"] == 1
    assert catalog["apple_hash"]["top_years"][0]["year"] == "2025"
    assert catalog["apple_hash"]["top_sections"][0] == {
        "section": "Note 2 - Revenue",
        "chunks": 2,
    }

    assert set(registry) == {"Apple", "Tesla"}
    assert registry["Apple"]["aliases"] == ["aapl", "apple", "apple inc"]
    assert registry["Apple"]["filenames"] == ["apple_fy2025_10k.pdf"]
    assert registry["Tesla"]["filenames"] == ["tesla_q4_2025_update.pdf"]


def test_unknown_customer_document_uses_generic_filename_fallback():
    tenant_id = "tenant_acme"
    chunks = [
        make_chunk(
            point_id="x1",
            tenant_id=tenant_id,
            filename="Acme_Logistics_2026_Report.pdf",
            document_hash="acme_hash",
            chunk_index=0,
            chunk_type="text",
            section="Overview",
            text="Warehouse performance in 2026.",
        )
    ]

    catalog, registry = build_document_catalog(chunks, tenant_id)

    assert catalog["acme_hash"]["entities"] == ["Acme Logistics 2026 Report"]
    assert registry["Acme Logistics 2026 Report"]["aliases"] == [
        "acme logistics 2026 report"
    ]

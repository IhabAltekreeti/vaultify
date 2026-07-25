import re

import numpy as np
import pytest

from vaultify.extensions import db
from vaultify.models import Document, Organization
from vaultify.services.ingestion import (
    CanonicalChunkerV2,
    deterministic_point_id,
    ingest_document,
    validate_pdf_upload,
)
from vaultify.web.app import create_app


class FakeTokenizer:
    def __init__(self):
        self._token_to_id = {}
        self._id_to_token = {}
        self._next_id = 1000

    def _tokens(self, text):
        return re.findall(r"\S+", str(text or ""))

    def _id(self, token):
        if token not in self._token_to_id:
            token_id = self._next_id
            self._next_id += 1
            self._token_to_id[token] = token_id
            self._id_to_token[token_id] = token
        return self._token_to_id[token]

    def __call__(self, text, *, add_special_tokens, **_kwargs):
        ids = [self._id(token) for token in self._tokens(text)]
        if add_special_tokens:
            ids = [101] + ids + [102]
        return {"input_ids": ids}

    def decode(self, token_ids, **_kwargs):
        return " ".join(
            self._id_to_token[token_id]
            for token_id in token_ids
            if token_id in self._id_to_token
        )


class FakeModel:
    max_seq_length = 256

    def __init__(self):
        self.tokenizer = FakeTokenizer()


class FakeEmbeddingService:
    def __init__(self):
        self.model = FakeModel()

    def encode_documents(self, texts, *, batch_size=32, show_progress_bar=False):
        assert batch_size == 64
        assert show_progress_bar is False
        return np.vstack(
            [np.full(384, index + 1, dtype=np.float32) for index, _ in enumerate(texts)]
        )


class FakeConvertedDocument:
    def __init__(self, markdown):
        self._markdown = markdown

    def export_to_markdown(self):
        return self._markdown


class FakeConversionResult:
    def __init__(self, markdown):
        self.document = FakeConvertedDocument(markdown)


class FakeConverter:
    def __init__(self, markdown):
        self.markdown = markdown
        self.paths = []

    def convert(self, path):
        self.paths.append(path)
        return FakeConversionResult(self.markdown)


class FakeQdrant:
    def __init__(self, *, fail_upsert=False):
        self.fail_upsert = fail_upsert
        self.delete_calls = []
        self.upsert_calls = []

    def delete(self, *, collection_name, points_selector, wait):
        self.delete_calls.append(
            {
                "collection_name": collection_name,
                "points_selector": points_selector,
                "wait": wait,
            }
        )

    def upsert(self, *, collection_name, points, wait):
        self.upsert_calls.append(
            {
                "collection_name": collection_name,
                "points": list(points),
                "wait": wait,
            }
        )
        if self.fail_upsert:
            raise RuntimeError("synthetic qdrant failure")


def test_pdf_validation_and_deterministic_point_ids():
    validated = validate_pdf_upload(
        "Quarterly Report.pdf",
        b"%PDF-1.7\nsynthetic regression pdf",
    )
    assert validated.safe_filename == "Quarterly_Report.pdf"
    assert len(validated.document_hash) == 64

    with pytest.raises(ValueError):
        validate_pdf_upload("report.txt", b"%PDF-1.7\ndata")
    with pytest.raises(ValueError):
        validate_pdf_upload("report.pdf", b"")
    with pytest.raises(ValueError):
        validate_pdf_upload("report.pdf", b"not-a-pdf")
    with pytest.raises(ValueError):
        validate_pdf_upload("report.pdf", b"%PDF-12345", max_size_bytes=4)

    point_a = deterministic_point_id("tenant-a", "hash-a", 7)
    point_b = deterministic_point_id("tenant-a", "hash-a", 7)
    point_c = deterministic_point_id("tenant-b", "hash-a", 7)
    assert point_a == point_b
    assert point_a != point_c


def test_canonical_chunker_v2_preserves_final_safety_invariants():
    chunker = CanonicalChunkerV2(FakeModel())
    long_text = " ".join(["financial-data"] * 700)
    huge_row = "| Oversized row | " + " ".join(["123456"] * 700) + " |"

    markdown = "\n".join(
        [
            "# Revenue",
            long_text,
            "",
            "| Metric | 2025 | 2024 |",
            "|---|---|---|",
            "| Total net sales | 416,161 | 391,035 |",
            huge_row,
            "",
            "# Duplicate",
            "| Metric | Value |",
            "|---|---|",
            "| Same | 1 |",
            "",
            "| Metric | Value |",
            "|---|---|",
            "| Same | 1 |",
        ]
    )

    chunks = chunker.chunk_markdown(markdown)
    assert chunks
    assert [chunk["chunk_index"] for chunk in chunks] == list(range(len(chunks)))
    assert max(chunker.count_embedding_tokens(chunk["text"]) for chunk in chunks) <= 240
    assert all("|---|" not in chunk["text"] for chunk in chunks)
    assert any(chunk["chunk_type"] == "table" for chunk in chunks)
    assert any("Section: Revenue" in chunk["text"] for chunk in chunks if chunk["chunk_type"] == "table")

    normalized = [re.sub(r"\s+", " ", chunk["text"]).strip() for chunk in chunks]
    assert len(normalized) == len(set(normalized))


def _make_app():
    return create_app(
        services={"answer_tenant_question": lambda **_kwargs: {"answer": "unused", "results": []}},
        config={
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "ingestion-regression-key",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        },
    )


def _make_document(organization, *, document_hash, filename="report.pdf"):
    document = Document(
        organization_id=organization.id,
        original_filename=filename,
        stored_filename=f"{document_hash[:12]}.pdf",
        storage_path=f"/tmp/{document_hash[:12]}.pdf",
        mime_type="application/pdf",
        size_bytes=123,
        document_hash=document_hash,
        status="uploaded",
    )
    db.session.add(document)
    db.session.commit()
    return document


def test_ingest_document_replaces_only_the_trusted_document_and_marks_ready():
    app = _make_app()
    markdown = (
        "# Revenue\n\n"
        "Dollars in millions.\n\n"
        "| Metric | 2025 | 2024 |\n"
        "|---|---|---|\n"
        "| Total net sales | 416,161 | 391,035 |"
    )

    with app.app_context():
        db.create_all()
        organization = Organization(
            name="Ingestion Organization",
            slug="ingestion-organization",
            tenant_id="tenant_ingestion",
        )
        db.session.add(organization)
        db.session.commit()

        document = _make_document(
            organization,
            document_hash="a" * 64,
            filename="Apple FY2025.pdf",
        )
        embeddings = FakeEmbeddingService()
        qdrant = FakeQdrant()

        chunk_count = ingest_document(
            document,
            embedding_service=embeddings,
            qdrant_client=qdrant,
            converter=FakeConverter(markdown),
        )

        assert chunk_count > 0
        assert document.status == "ready"
        assert document.chunk_count == chunk_count
        assert document.indexed_at is not None
        assert document.error_message is None
        assert len(qdrant.delete_calls) == 1
        assert qdrant.upsert_calls

        points = [
            point
            for call in qdrant.upsert_calls
            for point in call["points"]
        ]
        assert len(points) == chunk_count
        assert all(point.payload["tenant_id"] == "tenant_ingestion" for point in points)
        assert all(point.payload["document_hash"] == "a" * 64 for point in points)
        assert all(point.payload["filename"] == "Apple FY2025.pdf" for point in points)
        assert [point.payload["chunk_index"] for point in points] == list(range(chunk_count))


def test_ingest_document_cleans_partial_vectors_and_marks_failed():
    app = _make_app()

    with app.app_context():
        db.create_all()
        organization = Organization(
            name="Failure Organization",
            slug="failure-organization",
            tenant_id="tenant_failure",
        )
        db.session.add(organization)
        db.session.commit()

        document = _make_document(
            organization,
            document_hash="b" * 64,
            filename="Failure.pdf",
        )
        qdrant = FakeQdrant(fail_upsert=True)

        with pytest.raises(RuntimeError, match="synthetic qdrant failure"):
            ingest_document(
                document,
                embedding_service=FakeEmbeddingService(),
                qdrant_client=qdrant,
                converter=FakeConverter("# Test\n\nSome indexable document text."),
            )

        assert document.status == "failed"
        assert document.chunk_count == 0
        assert "synthetic qdrant failure" in document.error_message
        assert len(qdrant.delete_calls) == 2

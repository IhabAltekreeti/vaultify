"""Canonical Vaultify PDF ingestion core extracted from the approved golden runtime.

The release implementation preserves the final active Cell 20A/20C behavior while
replacing notebook globals and runtime monkey-patches with explicit dependencies.
The only post-golden hardening here is a bounded oversized-table-row fitting guard:
some tokenizers can decode a token slice into text that retokenizes to a few more
embedding tokens than the original slice. The guard shrinks only that oversized row
piece until the final serialized chunk is within the same 240-token limit.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass

from qdrant_client.models import (
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointStruct,
)
from werkzeug.utils import secure_filename

from vaultify.config import COLLECTION_NAME
from vaultify.extensions import db
from vaultify.models import utc_now


MAX_UPLOAD_SIZE_BYTES = 25 * 1024 * 1024
MAX_CHUNK_TOKENS = 240
SPECIAL_TOKEN_BUFFER = 2
TEXT_CHUNK_SIZE = 800
TEXT_CHUNK_OVERLAP = 120


@dataclass(frozen=True)
class ValidatedPdf:
    original_filename: str
    safe_filename: str
    file_bytes: bytes
    document_hash: str


def validate_pdf_upload(
    original_filename,
    pdf_bytes,
    *,
    max_size_bytes=MAX_UPLOAD_SIZE_BYTES,
):
    """Validate the same PDF invariants used by the golden upload/dry-run path."""
    original_filename = str(original_filename or "").strip()
    safe_filename = secure_filename(original_filename)
    pdf_bytes = bytes(pdf_bytes or b"")

    if not safe_filename or not safe_filename.lower().endswith(".pdf"):
        raise ValueError("The uploaded file must have a .pdf extension.")
    if not pdf_bytes:
        raise ValueError("The uploaded PDF is empty.")
    if len(pdf_bytes) > int(max_size_bytes):
        raise ValueError("The uploaded PDF exceeds the current 25 MB application limit.")
    if not pdf_bytes.startswith(b"%PDF-"):
        raise ValueError("The uploaded file has an invalid PDF signature.")

    try:
        import filetype
    except ImportError as error:  # pragma: no cover - dependency packaging gate
        raise RuntimeError(
            "The filetype package is required for PDF signature validation."
        ) from error

    detected_type = filetype.guess(pdf_bytes[:8192])
    if detected_type is not None and detected_type.mime != "application/pdf":
        raise ValueError("The uploaded file MIME signature is not PDF.")

    return ValidatedPdf(
        original_filename=original_filename,
        safe_filename=safe_filename,
        file_bytes=pdf_bytes,
        document_hash=hashlib.sha256(pdf_bytes).hexdigest(),
    )


class CanonicalChunkerV2:
    """Final approved seed-style, token-safe Vaultify Markdown chunker."""

    def __init__(self, model):
        if model is None or not hasattr(model, "tokenizer"):
            raise TypeError(
                "A sentence-transformer style model with a tokenizer is required."
            )

        self.model = model
        self.tokenizer = model.tokenizer
        max_seq_length = int(getattr(model, "max_seq_length", 256) or 256)
        self.max_chunk_tokens = min(MAX_CHUNK_TOKENS, max_seq_length - 16)
        self.token_payload_limit = self.max_chunk_tokens - SPECIAL_TOKEN_BUFFER
        self.max_table_prefix_tokens = min(96, self.token_payload_limit // 2)

        if self.max_chunk_tokens <= SPECIAL_TOKEN_BUFFER:
            raise ValueError(
                "Embedding model token limit is too small for Vaultify chunking."
            )

    def get_raw_token_ids(self, text):
        encoded = self.tokenizer(
            str(text or ""),
            add_special_tokens=False,
            truncation=False,
            return_attention_mask=False,
            return_token_type_ids=False,
            verbose=False,
        )
        token_ids = encoded["input_ids"]
        if token_ids and isinstance(token_ids[0], (list, tuple)):
            token_ids = token_ids[0]
        return list(token_ids)

    def count_raw_tokens(self, text):
        return len(self.get_raw_token_ids(text))

    def count_embedding_tokens(self, text):
        encoded = self.tokenizer(
            str(text or ""),
            add_special_tokens=True,
            truncation=False,
            return_attention_mask=False,
            return_token_type_ids=False,
            verbose=False,
        )
        token_ids = encoded["input_ids"]
        if token_ids and isinstance(token_ids[0], (list, tuple)):
            token_ids = token_ids[0]
        return len(token_ids)

    def decode_token_slice(self, token_ids):
        return self.tokenizer.decode(
            token_ids,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=True,
        ).strip()

    def truncate_to_token_limit(self, text, token_limit):
        text = str(text or "").strip()
        if not text or token_limit <= 0:
            return ""

        token_ids = self.get_raw_token_ids(text)
        if len(token_ids) <= token_limit:
            return text
        return self.decode_token_slice(token_ids[:token_limit])

    def split_to_token_safe_text(self, text, token_limit=None):
        text = str(text or "").strip()
        token_limit = token_limit or self.token_payload_limit
        if not text:
            return []

        token_ids = self.get_raw_token_ids(text)
        if len(token_ids) <= token_limit:
            return [text]

        pieces = []
        for start_index in range(0, len(token_ids), token_limit):
            decoded = self.decode_token_slice(
                token_ids[start_index : start_index + token_limit]
            )
            if decoded:
                pieces.append(decoded)
        return pieces

    @staticmethod
    def is_markdown_separator_row(line):
        stripped_line = str(line or "").strip()
        if not stripped_line.startswith("|"):
            return False

        cells = [cell.strip() for cell in stripped_line.strip("|").split("|")]
        if not cells:
            return False
        return all(bool(re.fullmatch(r":?-{3,}:?", cell)) for cell in cells)

    def build_safe_table_prefix(self, section, header_line):
        section = str(section or "").strip() or "Unknown section"
        header_line = str(header_line or "").strip()
        section_label = f"Section: {section}\nTable columns:\n"
        section_token_count = self.count_raw_tokens(section_label)

        if section_token_count >= self.max_table_prefix_tokens:
            return self.truncate_to_token_limit(
                section_label,
                self.max_table_prefix_tokens,
            )

        available_header_tokens = self.max_table_prefix_tokens - section_token_count
        compact_header = self.truncate_to_token_limit(
            header_line,
            available_header_tokens,
        )
        return (section_label + compact_header).strip()

    @staticmethod
    def create_chunk(text, chunk_type, section):
        return {
            "text": str(text or "").strip(),
            "chunk_type": chunk_type,
            "section": str(section or "").strip() or "Document content",
        }

    def split_normal_text(self, text, section):
        text = str(text or "").strip()
        if not text:
            return []

        chunks = []
        start_index = 0
        while start_index < len(text):
            end_index = min(start_index + TEXT_CHUNK_SIZE, len(text))
            character_piece = text[start_index:end_index].strip()

            for safe_piece in self.split_to_token_safe_text(character_piece):
                chunks.append(self.create_chunk(safe_piece, "text", section))

            if end_index >= len(text):
                break
            start_index = max(
                end_index - TEXT_CHUNK_OVERLAP,
                start_index + 1,
            )

        return chunks

    def split_oversized_table_row(self, row, table_prefix, section):
        """Split one oversized row while validating the final serialized token count.

        Golden Cell 20A budgeted the row using raw token IDs, decoded each slice, then
        re-tokenized the final prefix+row text. With a real WordPiece tokenizer that
        decode/re-tokenize round-trip is not guaranteed to be token-count idempotent.
        We therefore keep the same initial budget, but shrink only a failing row slice
        until the *final* serialized chunk fits. The next slice starts after exactly the
        original token IDs consumed by the accepted piece, so no row IDs are skipped.
        """
        prefix_with_newline = table_prefix.rstrip() + "\n"
        prefix_token_count = self.count_raw_tokens(prefix_with_newline)
        available_row_tokens = self.token_payload_limit - prefix_token_count

        if available_row_tokens <= 0:
            raise RuntimeError(
                "The table prefix consumed the complete token budget. "
                f"Section: {section}"
            )

        row_token_ids = self.get_raw_token_ids(row)
        chunks = []
        start_index = 0

        while start_index < len(row_token_ids):
            remaining_tokens = len(row_token_ids) - start_index
            slice_size = min(available_row_tokens, remaining_tokens)
            accepted_text = None
            accepted_size = None

            while slice_size > 0:
                token_slice = row_token_ids[
                    start_index : start_index + slice_size
                ]
                decoded_row = self.decode_token_slice(token_slice)

                if not decoded_row:
                    slice_size -= 1
                    continue

                candidate_text = (prefix_with_newline + decoded_row).strip()
                candidate_token_count = self.count_embedding_tokens(candidate_text)

                if candidate_token_count <= self.max_chunk_tokens:
                    accepted_text = candidate_text
                    accepted_size = slice_size
                    break

                overflow = candidate_token_count - self.max_chunk_tokens
                slice_size -= max(1, overflow)

            if accepted_text is None or accepted_size is None:
                raise RuntimeError(
                    "Unable to fit an oversized table-row piece within the token limit. "
                    f"Section: {section}"
                )

            chunks.append(
                self.create_chunk(
                    accepted_text,
                    "table",
                    section,
                )
            )
            start_index += accepted_size

        return chunks

    def split_table(self, table_lines, section):
        if not table_lines:
            return []

        cleaned_lines = [line.strip() for line in table_lines if line.strip()]
        if not cleaned_lines:
            return []

        header_line = cleaned_lines[0]
        if len(cleaned_lines) > 1 and self.is_markdown_separator_row(
            cleaned_lines[1]
        ):
            data_rows = cleaned_lines[2:]
        else:
            data_rows = cleaned_lines[1:]

        table_prefix = self.build_safe_table_prefix(section, header_line)
        chunks = []
        current_rows = []

        def build_table_text(rows):
            return (
                table_prefix.rstrip()
                + "\n"
                + "\n".join(rows)
            ).strip()

        def flush_current_rows():
            nonlocal current_rows
            if not current_rows:
                return

            chunk_text = build_table_text(current_rows)
            if self.count_embedding_tokens(chunk_text) > self.max_chunk_tokens:
                raise RuntimeError(
                    "An internal table chunk exceeded the 240-token limit."
                )

            chunks.append(self.create_chunk(chunk_text, "table", section))
            current_rows = []

        if not data_rows:
            for safe_piece in self.split_to_token_safe_text(table_prefix):
                chunks.append(self.create_chunk(safe_piece, "table", section))
            return chunks

        for row in data_rows:
            candidate_rows = current_rows + [row]
            candidate_text = build_table_text(candidate_rows)

            if self.count_embedding_tokens(candidate_text) <= self.max_chunk_tokens:
                current_rows = candidate_rows
                continue

            flush_current_rows()
            single_row_text = build_table_text([row])

            if self.count_embedding_tokens(single_row_text) <= self.max_chunk_tokens:
                current_rows = [row]
            else:
                chunks.extend(
                    self.split_oversized_table_row(
                        row,
                        table_prefix,
                        section,
                    )
                )

        flush_current_rows()
        return chunks

    def chunk_markdown(self, markdown_text):
        """Chunk Markdown with the final approved Cell 20A/20C behavior."""
        lines = str(markdown_text or "").splitlines()
        chunks = []
        current_section = "Document introduction"
        text_buffer = []

        def flush_text_buffer():
            nonlocal text_buffer
            buffered_text = "\n".join(text_buffer).strip()
            if buffered_text:
                chunks.extend(
                    self.split_normal_text(
                        buffered_text,
                        current_section,
                    )
                )
            text_buffer = []

        line_index = 0
        while line_index < len(lines):
            line = lines[line_index]
            stripped_line = line.strip()
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", stripped_line)

            if heading_match:
                flush_text_buffer()
                current_section = heading_match.group(2).strip()
                text_buffer.append(stripped_line)
                line_index += 1
                continue

            if stripped_line.startswith("|"):
                flush_text_buffer()
                table_lines = []
                while (
                    line_index < len(lines)
                    and lines[line_index].strip().startswith("|")
                ):
                    table_lines.append(lines[line_index])
                    line_index += 1

                chunks.extend(
                    self.split_table(
                        table_lines,
                        current_section,
                    )
                )
                continue

            text_buffer.append(line)
            line_index += 1

        flush_text_buffer()

        unique_chunks = []
        seen_hashes = set()

        for chunk in chunks:
            normalized_text = re.sub(r"\s+", " ", chunk["text"]).strip()
            if not normalized_text:
                continue

            chunk_hash = hashlib.sha256(
                normalized_text.encode("utf-8")
            ).hexdigest()
            if chunk_hash in seen_hashes:
                continue

            seen_hashes.add(chunk_hash)
            chunk["chunk_index"] = len(unique_chunks)
            unique_chunks.append(chunk)

        oversized = [
            chunk
            for chunk in unique_chunks
            if self.count_embedding_tokens(chunk["text"]) > self.max_chunk_tokens
        ]
        if oversized:
            raise RuntimeError(
                f"Canonical chunker generated {len(oversized)} oversized chunks."
            )

        return unique_chunks


def build_document_converter():
    """Build the same GPU-aware Docling converter used by the golden ingestion path."""
    import torch
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import (
        AcceleratorDevice,
        AcceleratorOptions,
        PdfPipelineOptions,
    )
    from docling.document_converter import DocumentConverter, PdfFormatOption

    pipeline_options = PdfPipelineOptions()
    if torch.cuda.is_available():
        pipeline_options.accelerator_options = AcceleratorOptions(
            num_threads=4,
            device=AcceleratorDevice.CUDA,
        )

    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options
            ),
        }
    )


def parse_pdf_to_markdown(storage_path, *, converter=None):
    converter = converter or build_document_converter()
    result = converter.convert(str(storage_path))
    markdown_text = result.document.export_to_markdown()

    if not str(markdown_text or "").strip():
        raise RuntimeError("Docling returned empty Markdown.")

    return str(markdown_text)


def build_document_filter(tenant_id, document_hash):
    return Filter(
        must=[
            FieldCondition(
                key="tenant_id",
                match=MatchValue(value=str(tenant_id)),
            ),
            FieldCondition(
                key="document_hash",
                match=MatchValue(value=str(document_hash)),
            ),
        ]
    )


def delete_document_vectors(
    qdrant_client,
    tenant_id,
    document_hash,
    *,
    collection_name=COLLECTION_NAME,
):
    qdrant_client.delete(
        collection_name=collection_name,
        points_selector=FilterSelector(
            filter=build_document_filter(
                tenant_id,
                document_hash,
            )
        ),
        wait=True,
    )


def deterministic_point_id(tenant_id, document_hash, chunk_index):
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"{tenant_id}:{document_hash}:{int(chunk_index)}",
        )
    )


def build_qdrant_points(
    tenant_id,
    document_hash,
    filename,
    chunks,
    vectors,
):
    points = []

    for chunk_index, (chunk, vector) in enumerate(zip(chunks, vectors)):
        vector_list = vector.tolist() if hasattr(vector, "tolist") else list(vector)
        points.append(
            PointStruct(
                id=deterministic_point_id(
                    tenant_id,
                    document_hash,
                    chunk_index,
                ),
                vector=vector_list,
                payload={
                    "tenant_id": str(tenant_id),
                    "document_hash": str(document_hash),
                    "filename": str(filename),
                    "chunk_index": chunk_index,
                    "chunk_type": chunk["chunk_type"],
                    "section": chunk["section"],
                    "text": chunk["text"],
                },
            )
        )

    return points


def ingest_document(
    document,
    *,
    embedding_service,
    qdrant_client,
    collection_name=COLLECTION_NAME,
    converter=None,
    chunker=None,
    batch_size=100,
    show_progress_bar=False,
):
    """Parse, canonical-chunk, embed and safely replace one document's Qdrant points."""
    document.status = "parsing"
    document.error_message = None
    db.session.commit()

    tenant_id = document.organization.tenant_id
    document_hash = document.document_hash

    try:
        markdown_text = parse_pdf_to_markdown(
            document.storage_path,
            converter=converter,
        )
        chunker = chunker or CanonicalChunkerV2(embedding_service.model)
        chunks = chunker.chunk_markdown(markdown_text)

        if not chunks:
            raise RuntimeError("The PDF produced no indexable chunks.")

        document.status = "indexing"
        db.session.commit()

        vectors = embedding_service.encode_documents(
            [chunk["text"] for chunk in chunks],
            batch_size=64,
            show_progress_bar=show_progress_bar,
        )

        delete_document_vectors(
            qdrant_client,
            tenant_id,
            document_hash,
            collection_name=collection_name,
        )

        points = build_qdrant_points(
            tenant_id,
            document_hash,
            document.original_filename,
            chunks,
            vectors,
        )

        for batch_start in range(0, len(points), int(batch_size)):
            qdrant_client.upsert(
                collection_name=collection_name,
                points=points[
                    batch_start : batch_start + int(batch_size)
                ],
                wait=True,
            )

        document.status = "ready"
        document.chunk_count = len(points)
        document.indexed_at = utc_now()
        document.error_message = None
        db.session.commit()
        return len(points)

    except Exception as error:
        try:
            delete_document_vectors(
                qdrant_client,
                tenant_id,
                document_hash,
                collection_name=collection_name,
            )
        except Exception:
            pass

        document.status = "failed"
        document.chunk_count = 0
        document.error_message = f"{type(error).__name__}: {error}"[:500]
        db.session.commit()
        raise

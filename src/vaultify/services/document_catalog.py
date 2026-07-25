"""Tenant document catalog and entity-registry helpers for Vaultify."""

from collections import Counter, defaultdict
from pathlib import Path
import re


YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")


def normalize_catalog_text(text):
    normalized = str(text or "").lower()
    normalized = re.sub(r"[_\-]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def infer_document_entities(filename, chunks, *, entity_rules=None):
    """Infer document entities using optional caller-supplied rules.

    When no rule matches, fall back to a readable entity name derived from
    the filename. This keeps the application runtime generic for arbitrary
    customer documents.
    """
    entity_rules = entity_rules or {}
    normalized_filename = normalize_catalog_text(filename)
    sample_content = " ".join(chunk["text"] for chunk in chunks[:20])
    normalized_content = normalize_catalog_text(sample_content)

    detected_entities = []

    for entity, rule in entity_rules.items():
        filename_match = any(
            term in normalized_filename
            for term in rule.get("filename_terms", set())
        )
        content_match = any(
            term in normalized_content
            for term in rule.get("content_terms", set())
        )

        if filename_match or content_match:
            detected_entities.append(entity)

    if not detected_entities:
        fallback_name = Path(filename).stem
        fallback_name = re.sub(r"[_\-]+", " ", fallback_name)
        fallback_name = re.sub(r"\s+", " ", fallback_name).strip()
        detected_entities.append(fallback_name or "Unknown entity")

    return detected_entities


def aliases_for_entities(entities, *, entity_rules=None):
    entity_rules = entity_rules or {}
    aliases = set()

    for entity in entities:
        rule = entity_rules.get(entity)
        if rule:
            aliases.update(rule.get("aliases", set()))
        else:
            aliases.add(normalize_catalog_text(entity))

    return sorted(aliases)


def build_document_catalog(chunks, tenant_id, *, entity_rules=None):
    """Build the golden Cell 21A-style document catalog for one tenant."""
    if not tenant_id:
        raise ValueError("A tenant ID is required to build the document catalog.")
    if not chunks:
        raise ValueError("At least one tenant chunk is required.")

    entity_rules = entity_rules or {}
    document_groups = defaultdict(list)

    for chunk in chunks:
        document_hash = chunk.get("document_hash")
        filename = str(chunk.get("filename") or "unknown_document")
        document_key = (
            document_hash
            if document_hash
            else f"filename::{filename.lower()}"
        )
        document_groups[document_key].append(chunk)

    document_catalog = {}
    entity_registry = defaultdict(
        lambda: {
            "aliases": set(),
            "document_keys": set(),
            "filenames": set(),
        }
    )

    for document_key, document_chunks in document_groups.items():
        document_chunks = sorted(
            document_chunks,
            key=lambda chunk: (
                int(chunk.get("chunk_index", 0)),
                str(chunk.get("point_id", "")),
            ),
        )

        filename_counts = Counter(
            str(chunk.get("filename") or "unknown_document")
            for chunk in document_chunks
        )
        filename = filename_counts.most_common(1)[0][0]

        document_hash = next(
            (
                chunk.get("document_hash")
                for chunk in document_chunks
                if chunk.get("document_hash")
            ),
            None,
        )

        chunk_type_counts = Counter(
            str(chunk.get("chunk_type") or "unknown")
            for chunk in document_chunks
        )
        section_counts = Counter(
            str(chunk.get("section"))
            for chunk in document_chunks
            if chunk.get("section")
        )

        year_counts = Counter()
        for chunk in document_chunks:
            year_counts.update(YEAR_PATTERN.findall(str(chunk.get("text") or "")))

        entities = infer_document_entities(
            filename,
            document_chunks,
            entity_rules=entity_rules,
        )
        aliases = aliases_for_entities(
            entities,
            entity_rules=entity_rules,
        )

        catalog_entry = {
            "document_key": document_key,
            "filename": filename,
            "document_hash": document_hash,
            "tenant_id": tenant_id,
            "chunk_count": len(document_chunks),
            "chunk_types": dict(chunk_type_counts),
            "entities": entities,
            "aliases": aliases,
            "top_years": [
                {"year": year, "mentions": count}
                for year, count in year_counts.most_common(10)
            ],
            "top_sections": [
                {"section": section, "chunks": count}
                for section, count in section_counts.most_common(12)
            ],
            "chunks": document_chunks,
        }
        document_catalog[document_key] = catalog_entry

        for entity in entities:
            registry_entry = entity_registry[entity]
            registry_entry["aliases"].update(aliases)
            registry_entry["document_keys"].add(document_key)
            registry_entry["filenames"].add(filename)

    stable_registry = {
        entity: {
            "aliases": sorted(metadata["aliases"]),
            "document_keys": sorted(metadata["document_keys"]),
            "filenames": sorted(metadata["filenames"]),
        }
        for entity, metadata in entity_registry.items()
    }

    return document_catalog, stable_registry

"""Stable Vaultify configuration constants extracted from the golden notebook."""

PROJECT_NAME = "Vaultify"

COLLECTION_NAME = "vaultify_v3_documents"

TENANT_ID_FIELD = "tenant_id"
DOCUMENT_HASH_FIELD = "document_hash"
FILENAME_FIELD = "filename"
CHUNK_INDEX_FIELD = "chunk_index"
CHUNK_TYPE_FIELD = "chunk_type"
TEXT_FIELD = "text"

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
VECTOR_SIZE = 384
LLM_MODEL = "llama-3.3-70b-versatile"

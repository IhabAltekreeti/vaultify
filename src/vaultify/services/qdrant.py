"""Qdrant client factory for Vaultify."""

from qdrant_client import QdrantClient


def create_qdrant_client(*, url, api_key, timeout=60):
    """Create the Qdrant client using the golden runtime timeout by default."""
    if not url:
        raise ValueError("QDRANT_URL is required.")
    if not api_key:
        raise ValueError("QDRANT_API_KEY is required.")

    return QdrantClient(url=url, api_key=api_key, timeout=timeout)


def list_collection_names(client):
    return [collection.name for collection in client.get_collections().collections]

"""Qdrant client factory for Vaultify."""

from qdrant_client import QdrantClient


def create_qdrant_client(*, url, api_key):
    if not url:
        raise ValueError("QDRANT_URL is required.")
    if not api_key:
        raise ValueError("QDRANT_API_KEY is required.")

    return QdrantClient(url=url, api_key=api_key)


def list_collection_names(client):
    return [collection.name for collection in client.get_collections().collections]

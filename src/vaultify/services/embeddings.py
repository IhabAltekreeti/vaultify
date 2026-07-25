"""Embedding service extracted from the Vaultify golden notebook."""

from sentence_transformers import SentenceTransformer

from vaultify.config import EMBEDDING_MODEL_NAME, VECTOR_SIZE


class EmbeddingService:
    """Small wrapper around the canonical Vaultify embedding model."""

    def __init__(self, model_name=EMBEDDING_MODEL_NAME):
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)

    def encode_documents(self, texts, *, batch_size=32, show_progress_bar=False):
        vectors = self.model.encode(
            list(texts),
            batch_size=batch_size,
            show_progress_bar=show_progress_bar,
        )
        self._validate_dimension(vectors)
        return vectors

    def encode_query(self, question):
        vector = self.model.encode(question)
        self._validate_dimension(vector)
        return vector

    @staticmethod
    def _validate_dimension(vectors):
        if getattr(vectors, "ndim", 1) == 1:
            dimension = len(vectors)
        else:
            dimension = vectors.shape[-1]

        if dimension != VECTOR_SIZE:
            raise ValueError(
                f"Unexpected embedding dimension: {dimension}; expected {VECTOR_SIZE}."
            )

"""Text embeddings (spec section 3): a small local sentence-transformers model, 384 dimensions."""

from collections.abc import Sequence
from typing import Protocol


class Embedder(Protocol):
    def embed_many(self, texts: Sequence[str]) -> list[list[float]]: ...


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str, expected_dim: int) -> None:
        # Importing sentence_transformers pulls in torch, so keep it out of module import time.
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)
        actual_dim = int(self._model.encode("dimension probe").shape[0])
        if actual_dim != expected_dim:
            raise ValueError(f"{model_name} produces {actual_dim}-dim vectors but EMBEDDING_DIM is {expected_dim}")

    def embed_many(self, texts: Sequence[str]) -> list[list[float]]:
        return self._model.encode(list(texts), normalize_embeddings=True, show_progress_bar=False).tolist()

"""Scripture storage and hard-filtered semantic search (spec sections 3 and 5), backed by Qdrant."""

import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from qdrant_client import QdrantClient, models

from app.config import Settings
from app.schemas import ScriptureRecord

# Qdrant point ids must be unsigned ints or UUIDs, so the spec's string ids ("bible-psalm-147-3")
# are mapped to stable UUIDs; the original id stays in the payload.
_ID_NAMESPACE = uuid.UUID("2b0a4a5e-6a1c-4d3e-9a54-4f5d4a1c0c11")
_BELIEF_SYSTEMS_TTL_SECONDS = 60.0


def _point_id(scripture_id: str) -> str:
    return str(uuid.uuid5(_ID_NAMESPACE, scripture_id))


@dataclass(frozen=True)
class ScriptureMatch:
    id: str
    belief_system: str
    source_book: str
    content: str
    score: float


class ScriptureStore:
    def __init__(self, client: QdrantClient, collection: str, dim: int, *, remote: bool = False) -> None:
        self._client = client
        self._collection = collection
        self._dim = dim
        self._remote = remote
        self._belief_systems_cache: tuple[float, list[str]] | None = None

    @classmethod
    def from_settings(cls, settings: Settings) -> "ScriptureStore":
        """Qdrant server when QDRANT_URL is set, otherwise embedded on-disk Qdrant (single process)."""
        if settings.qdrant_url:
            client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
        else:
            settings.qdrant_path.mkdir(parents=True, exist_ok=True)
            client = QdrantClient(path=str(settings.qdrant_path))
        return cls(client, settings.qdrant_collection, settings.embedding_dim, remote=bool(settings.qdrant_url))

    def ensure_collection(self, *, recreate: bool = False) -> None:
        if recreate and self._client.collection_exists(self._collection):
            self._client.delete_collection(self._collection)
        if not self._client.collection_exists(self._collection):
            self._client.create_collection(
                self._collection,
                vectors_config=models.VectorParams(size=self._dim, distance=models.Distance.COSINE),
            )
        else:
            size = self._client.get_collection(self._collection).config.params.vectors.size
            if size != self._dim:
                raise ValueError(
                    f"Collection '{self._collection}' stores {size}-dim vectors but EMBEDDING_DIM is {self._dim}. "
                    "Re-run the ingest script with --recreate."
                )
        if self._remote:  # embedded Qdrant ignores payload indexes
            self._client.create_payload_index(self._collection, "belief_system", models.PayloadSchemaType.KEYWORD)

    def upsert(self, records: Sequence[ScriptureRecord], vectors: Sequence[Sequence[float]]) -> None:
        points = [
            models.PointStruct(id=_point_id(record.id), vector=list(vector), payload=record.model_dump())
            for record, vector in zip(records, vectors, strict=True)
        ]
        self._client.upsert(self._collection, points=points)
        self._belief_systems_cache = None

    def search(self, vector: Sequence[float], belief_system: str) -> ScriptureMatch | None:
        """Best match within `belief_system` only. The filter is applied inside the vector search, so
        passages from other belief systems can never be returned, however similar they are."""
        response = self._client.query_points(
            self._collection,
            query=list(vector),
            query_filter=models.Filter(
                must=[models.FieldCondition(key="belief_system", match=models.MatchValue(value=belief_system))]
            ),
            limit=1,
            with_payload=True,
        )
        if not response.points:
            return None
        hit = response.points[0]
        payload = hit.payload or {}
        return ScriptureMatch(
            id=payload["id"],
            belief_system=payload["belief_system"],
            source_book=payload["source_book"],
            content=payload["content"],
            score=hit.score,
        )

    def list_belief_systems(self) -> list[str]:
        cached = self._belief_systems_cache
        if cached and time.monotonic() - cached[0] < _BELIEF_SYSTEMS_TTL_SECONDS:
            return cached[1]
        found: set[str] = set()
        offset = None
        while True:
            records, offset = self._client.scroll(
                self._collection, limit=500, offset=offset, with_payload=["belief_system"], with_vectors=False
            )
            found.update(record.payload["belief_system"] for record in records if record.payload)
            if offset is None:
                break
        result = sorted(found)
        self._belief_systems_cache = (time.monotonic(), result)
        return result

    def count(self) -> int:
        return self._client.count(self._collection, exact=True).count

    def close(self) -> None:
        self._client.close()

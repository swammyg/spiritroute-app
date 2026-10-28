"""Test doubles: no model download, no network, no server."""

import hashlib
import json
import re
from collections.abc import Sequence

from qdrant_client import QdrantClient

from app.ingest import ingest
from app.schemas import ScriptureRecord
from app.services.embedding import Embedder
from app.services.vector_store import ScriptureStore

DIM = 384

# Fictional traditions and text, so no test depends on (or could be mistaken for) real scripture.
ALPHA_NEAR = ScriptureRecord(
    id="alpha-near",
    belief_system="Faith-Alpha",
    source_book="Alpha Scroll 1:1",
    content="A sad family that finds belonging at last.",
)
ALPHA_FAR = ScriptureRecord(
    id="alpha-far",
    belief_system="Faith-Alpha",
    source_book="Alpha Scroll 2:2",
    content="Gratitude and joy for every purpose.",
)
# Word for word the search query for Sad + Family + Belonging, so it is the best match in the whole
# collection. A search for Faith-Alpha must still never return it.
BETA_EXACT = ScriptureRecord(
    id="beta-exact",
    belief_system="Faith-Beta",
    source_book="Beta Book 9:9",
    content="Feeling Sad because of an issue with my Family involving a lack of Belonging.",
)
RECORDS = [ALPHA_NEAR, ALPHA_FAR, BETA_EXACT]


class FakeEmbedder:
    """Bag-of-words hashing embedder: texts that share words get similar vectors."""

    def embed(self, text: str) -> list[float]:
        return self._vector(text)

    def embed_many(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    @staticmethod
    def _vector(text: str) -> list[float]:
        vector = [0.0] * DIM
        for token in re.findall(r"[a-z]+", text.lower()):
            vector[int(hashlib.sha1(token.encode()).hexdigest(), 16) % DIM] += 1.0
        norm = sum(value * value for value in vector) ** 0.5 or 1.0
        return [value / norm for value in vector]


class RecordingEmbedder(FakeEmbedder):
    """Remembers every text it was asked to embed."""

    def __init__(self) -> None:
        self.texts: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.texts.append(text)
        return super().embed(text)

    def embed_many(self, texts: Sequence[str]) -> list[list[float]]:
        texts = list(texts)
        self.texts.extend(texts)
        return super().embed_many(texts)


class ScriptedEmbedder:
    """Returns exactly the vector it was given for each text, so a test controls the geometry."""

    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self.vectors = vectors

    def embed_many(self, texts: Sequence[str]) -> list[list[float]]:
        return [list(self.vectors[text]) for text in texts]


class FakeLLM:
    """Replies in order (a str is returned, an Exception is raised), repeating the last reply."""

    def __init__(self, *replies: str | Exception) -> None:
        self.replies = replies
        self.calls: list[tuple[str, str]] = []
        self.closed = False

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        reply = self.replies[min(len(self.calls), len(self.replies)) - 1]
        if isinstance(reply, Exception):
            raise reply
        return reply

    async def aclose(self) -> None:
        self.closed = True


def llm_reply(
    word_of_hope: str = "This verse meets you where you are.",
    prayer_reflection: str = "May I find peace.\nMay I be held.",
) -> str:
    return json.dumps({"word_of_hope": word_of_hope, "prayer_reflection": prayer_reflection})


def make_store(embedder: Embedder | None = None, records: Sequence[ScriptureRecord] = RECORDS) -> ScriptureStore:
    embedder = embedder or FakeEmbedder()
    store = ScriptureStore(QdrantClient(":memory:"), "test_scriptures", DIM)
    ingest(records, embedder, store, recreate=False)  # the real load path, so tests embed what production embeds
    return store


class SpyStore:
    """Wraps a store and counts searches."""

    def __init__(self, inner: ScriptureStore) -> None:
        self.inner = inner
        self.searches = 0

    def search(self, vector: Sequence[float], belief_system: str):
        self.searches += 1
        return self.inner.search(vector, belief_system)

    def __getattr__(self, name: str):
        return getattr(self.inner, name)


class FailingStore:
    def search(self, vector: Sequence[float], belief_system: str):
        raise RuntimeError("database is down")

    def count(self) -> int:
        return 1

    def close(self) -> None:
        pass

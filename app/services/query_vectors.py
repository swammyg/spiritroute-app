"""Search vectors for every possible wizard answer, computed once at startup (spec section 5).

There are only 64 valid combinations of answers, so their query sentences are embedded up front and a
request is a dictionary lookup: no request runs the embedding model.

Centering: the 64 sentences share most of their wording ("Feeling ... because of an issue with my ...
involving a lack of ..."). In embedding space that shared part is a large common component, and it
pulls every answer toward the same few passages whatever the emotion, circle or driver. Subtracting the
mean of all 64 query vectors removes what they have in common, so only what differs between answers
steers the search. The query text itself is unchanged. QUERY_CENTERING=false searches with the raw
embeddings instead.
"""

import math
from collections.abc import Sequence

from app.diagnostic import all_answers, build_search_query
from app.schemas import Circle, Driver, Emotion
from app.services.embedding import Embedder


def center(vectors: Sequence[Sequence[float]]) -> list[list[float]]:
    """Subtract the mean vector from every vector, then scale each result to unit length."""
    mean = [sum(column) / len(vectors) for column in zip(*vectors, strict=True)]
    centered = []
    for vector in vectors:
        shifted = [value - average for value, average in zip(vector, mean, strict=True)]
        norm = math.sqrt(sum(value * value for value in shifted))
        if norm == 0:
            raise ValueError("a query vector equals the mean of all query vectors, so it cannot be centered")
        centered.append([value / norm for value in shifted])
    return centered


class QueryVectors:
    def __init__(self, embedder: Embedder, *, center_queries: bool) -> None:
        answers = all_answers()
        vectors = embedder.embed_many([build_search_query(*answer) for answer in answers])
        if center_queries:
            vectors = center(vectors)
        self._by_answer = dict(zip(answers, vectors, strict=True))

    def for_answer(self, emotion: Emotion, circle: Circle, driver: Driver) -> list[float]:
        return self._by_answer[(emotion, circle, driver)]

import asyncio
import math

import pytest

from app.config import Settings
from app.dependencies import build_services
from app.diagnostic import all_answers, build_search_query
from app.schemas import Circle, Driver, Emotion, ScriptureRecord
from app.services.query_vectors import QueryVectors, center
from tests.fakes import DIM, FakeEmbedder, RecordingEmbedder, ScriptedEmbedder, make_store

SAD_FAMILY_BELONGING = (Emotion.SAD, Circle.FAMILY, Driver.BELONGING)


def norm(vector) -> float:
    return math.sqrt(sum(value * value for value in vector))


def one_hot(index: int) -> list[float]:
    vector = [0.0] * DIM
    vector[index] = 1.0
    return vector


# --- the vectors --------------------------------------------------------------------------------


def test_every_valid_answer_has_a_unit_length_vector():
    queries = QueryVectors(FakeEmbedder(), center_queries=True)
    for answer in all_answers():
        vector = queries.for_answer(*answer)
        assert len(vector) == DIM
        assert norm(vector) == pytest.approx(1.0)


def test_the_64_search_sentences_are_embedded_once_each_at_startup():
    recording = RecordingEmbedder()
    QueryVectors(recording, center_queries=True)
    assert recording.texts == [build_search_query(*answer) for answer in all_answers()]
    assert len(set(recording.texts)) == 64
    assert "Feeling Sad because of an issue with my Family involving a lack of Belonging." in recording.texts
    assert "Feeling Happy about my Friends, and wanting to grow in Gratitude." in recording.texts


def test_looking_up_an_answer_does_not_run_the_embedder_again():
    recording = RecordingEmbedder()
    queries = QueryVectors(recording, center_queries=True)
    embedded = len(recording.texts)
    queries.for_answer(*SAD_FAMILY_BELONGING)
    assert len(recording.texts) == embedded


def test_without_centering_the_vectors_are_the_embedders_own():
    embedder = FakeEmbedder()
    expected = embedder.embed_many([build_search_query(*SAD_FAMILY_BELONGING)])[0]
    assert QueryVectors(embedder, center_queries=False).for_answer(*SAD_FAMILY_BELONGING) == expected


def test_build_services_passes_the_centering_setting_through(monkeypatch, tmp_path):
    monkeypatch.setattr("app.dependencies.SentenceTransformerEmbedder", lambda *args, **kwargs: FakeEmbedder())
    vectors = {}
    for centered in (False, True):
        settings = Settings(
            _env_file=None, qdrant_path=tmp_path / f"qdrant-{centered}", llm_enabled=False, query_centering=centered
        )
        services = build_services(settings)
        vectors[centered] = services.queries.for_answer(*SAD_FAMILY_BELONGING)
        asyncio.run(services.aclose())
    raw = FakeEmbedder().embed_many([build_search_query(*SAD_FAMILY_BELONGING)])[0]
    assert vectors[False] == raw
    assert vectors[True] != raw


# --- centering ----------------------------------------------------------------------------------


def test_centering_removes_the_component_every_vector_shares():
    # Axis 0 stands for the shared wording; axes 1-4 are what belongs to each vector alone.
    vectors = [[10.0] + [1.0 if axis == own else 0.0 for axis in range(4)] for own in range(4)]
    centered = center(vectors)
    assert all(vector[0] == pytest.approx(0.0, abs=1e-12) for vector in centered)
    assert all(norm(vector) == pytest.approx(1.0) for vector in centered)
    cosine_before = sum(a * b for a, b in zip(vectors[0], vectors[1], strict=True)) / (
        norm(vectors[0]) * norm(vectors[1])
    )
    cosine_after = sum(a * b for a, b in zip(centered[0], centered[1], strict=True))
    assert cosine_before > 0.95  # nearly parallel only because of the shared part
    assert cosine_after < 0


def test_identical_vectors_cannot_be_centered():
    with pytest.raises(ValueError, match="cannot be centered"):
        center([[1.0, 2.0], [1.0, 2.0]])


def test_centering_stops_a_wording_only_passage_from_winning_every_search():
    answers = all_answers()
    # Each query vector is a big part from the wording they all share (axis 0) plus a part that is theirs alone.
    vectors = {}
    for position, answer in enumerate(answers):
        vector = one_hot(1 + position)
        vector[0] = 10.0
        vectors[build_search_query(*answer)] = vector
    wording = ScriptureRecord(
        id="wording", belief_system="Faith-Alpha", source_book="W 1:1", content="Wording passage."
    )
    topical = ScriptureRecord(
        id="topical", belief_system="Faith-Alpha", source_book="T 1:1", content="Topical passage."
    )
    vectors[wording.embedding_text] = one_hot(0)
    vectors[topical.embedding_text] = one_hot(1 + answers.index(SAD_FAMILY_BELONGING))
    embedder = ScriptedEmbedder(vectors)
    store = make_store(embedder, records=[wording, topical])

    raw = QueryVectors(embedder, center_queries=False).for_answer(*SAD_FAMILY_BELONGING)
    centered = QueryVectors(embedder, center_queries=True).for_answer(*SAD_FAMILY_BELONGING)

    assert store.search(raw, "Faith-Alpha").id == "wording"
    assert store.search(centered, "Faith-Alpha").id == "topical"

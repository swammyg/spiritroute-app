import json
from pathlib import Path

import pytest
from qdrant_client import QdrantClient

from app.ingest import ingest, load_records
from app.schemas import Driver, ScriptureRecord
from app.services.vector_store import ScriptureStore
from tests.fakes import DIM, RECORDS, FakeEmbedder, make_store

SAMPLE_DATA = Path(__file__).resolve().parent.parent / "data" / "scriptures.sample.jsonl"
SAMPLE_DRIVERS = SAMPLE_DATA.with_suffix(".drivers.json")


def record_line(**overrides) -> str:
    base = {"id": "a-1", "belief_system": "Faith-Alpha", "source_book": "Alpha 1:1", "content": "Text."}
    return json.dumps({**base, **overrides})


def write_jsonl(tmp_path, *lines: str) -> Path:
    path = tmp_path / "scriptures.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# --- store --------------------------------------------------------------------------------------


def test_search_only_considers_the_requested_belief_system():
    embedder = FakeEmbedder()
    store = make_store(embedder)
    query = embedder.embed(RECORDS[2].content)  # identical to Faith-Beta's passage
    assert store.search(query, "Faith-Beta").id == "beta-exact"
    assert store.search(query, "Faith-Alpha").belief_system == "Faith-Alpha"


def test_search_returns_none_for_an_unknown_belief_system():
    embedder = FakeEmbedder()
    assert make_store(embedder).search(embedder.embed("anything"), "Faith-Gamma") is None


def test_search_returns_the_stored_fields_verbatim():
    embedder = FakeEmbedder()
    match = make_store(embedder).search(embedder.embed(RECORDS[0].content), "Faith-Alpha")
    assert (match.id, match.source_book, match.content) == (RECORDS[0].id, RECORDS[0].source_book, RECORDS[0].content)


def test_upserting_the_same_id_replaces_instead_of_duplicating():
    embedder = FakeEmbedder()
    store = make_store(embedder)
    edited = RECORDS[0].model_copy(update={"content": "Replacement text."})
    store.upsert([edited], embedder.embed_many([edited.content]))
    assert store.count() == 3
    assert store.search(embedder.embed("Replacement text."), "Faith-Alpha").content == "Replacement text."


def test_belief_system_list_refreshes_after_new_records_are_added():
    embedder = FakeEmbedder()
    store = make_store(embedder)
    assert store.list_belief_systems() == ["Faith-Alpha", "Faith-Beta"]
    gamma = ScriptureRecord(id="g-1", belief_system="Faith-Gamma", source_book="Gamma 1:1", content="Gamma text.")
    store.upsert([gamma], embedder.embed_many([gamma.content]))
    assert store.list_belief_systems() == ["Faith-Alpha", "Faith-Beta", "Faith-Gamma"]


def test_an_existing_collection_with_the_wrong_dimension_is_rejected():
    client = QdrantClient(":memory:")
    ScriptureStore(client, "scriptures", DIM).ensure_collection()
    with pytest.raises(ValueError, match="EMBEDDING_DIM"):
        ScriptureStore(client, "scriptures", 128).ensure_collection()


# --- ingest -------------------------------------------------------------------------------------


def test_ingest_round_trips_text_exactly():
    embedder = FakeEmbedder()
    store = ScriptureStore(QdrantClient(":memory:"), "scriptures", DIM)
    text = "He said, “Be still.” Don’t fear — I am here. Amen."
    record = ScriptureRecord(id="x-1", belief_system="Faith-Alpha", source_book="X 1:1", content=text)
    ingest([record], embedder, store, recreate=False)
    assert store.search(embedder.embed(text), "Faith-Alpha").content == text


def test_ingest_recreate_starts_from_an_empty_collection():
    embedder = FakeEmbedder()
    store = make_store(embedder)
    ingest(RECORDS[:1], embedder, store, recreate=True)
    assert store.count() == 1


def test_ingest_without_recreate_keeps_existing_records():
    embedder = FakeEmbedder()
    store = make_store(embedder)
    ingest(RECORDS[:1], embedder, store, recreate=False)
    assert store.count() == 3


def test_load_records_reads_jsonl_and_skips_blank_lines(tmp_path):
    path = write_jsonl(tmp_path, record_line(), "", record_line(id="a-2"))
    assert [record.id for record in load_records(path)] == ["a-1", "a-2"]


def test_load_records_names_the_offending_line(tmp_path):
    path = write_jsonl(tmp_path, record_line(), record_line(id="a-2", content=""))
    with pytest.raises(ValueError, match=r"line 2: .* at content"):
        load_records(path)


def test_load_records_rejects_unknown_fields(tmp_path):
    with pytest.raises(ValueError, match="translation"):
        load_records(write_jsonl(tmp_path, record_line(translation="KJV")))


def test_load_records_rejects_malformed_json(tmp_path):
    with pytest.raises(ValueError, match="line 1"):
        load_records(write_jsonl(tmp_path, "{not json"))


def test_load_records_rejects_duplicate_ids(tmp_path):
    with pytest.raises(ValueError, match="duplicate ids: a-1"):
        load_records(write_jsonl(tmp_path, record_line(), record_line()))


def test_load_records_rejects_an_empty_file(tmp_path):
    with pytest.raises(ValueError, match="no records"):
        load_records(write_jsonl(tmp_path, ""))


def test_shipped_sample_data_is_valid():
    records = load_records(SAMPLE_DATA)
    assert len(records) >= 40
    assert {record.belief_system for record in records} == {"Christianity"}
    assert all("\n" not in record.content and "  " not in record.content for record in records)
    assert all(record.themes for record in records)


def test_shipped_intended_drivers_label_every_sample_passage():
    labels = json.loads(SAMPLE_DRIVERS.read_text(encoding="utf-8"))
    assert set(labels) == {record.source_book for record in load_records(SAMPLE_DATA)}
    assert set(labels.values()) <= {driver.value for driver in Driver}


# --- themes -------------------------------------------------------------------------------------


def test_themes_are_optional_and_blank_means_none():
    plain = ScriptureRecord(id="t-1", belief_system="Faith-Alpha", source_book="T 1:1", content="Plain words.")
    blank = ScriptureRecord(
        id="t-2", belief_system="Faith-Alpha", source_book="T 2:2", content="Plain words.", themes="   "
    )
    assert plain.themes is None
    assert blank.themes is None


def test_embedding_text_puts_themes_before_the_passage():
    tagged = ScriptureRecord(
        id="t-1", belief_system="Faith-Alpha", source_book="T 1:1", content="Plain words.", themes="quokka, courage"
    )
    assert tagged.embedding_text == "Themes: quokka, courage\n\nPlain words."


def test_embedding_text_without_themes_is_just_the_passage():
    plain = ScriptureRecord(id="t-1", belief_system="Faith-Alpha", source_book="T 1:1", content="Plain words.")
    assert plain.embedding_text == "Plain words."


def test_load_records_reads_themes(tmp_path):
    records = load_records(write_jsonl(tmp_path, record_line(themes="grief, healing")))
    assert records[0].themes == "grief, healing"


def test_themes_make_a_passage_findable_but_are_never_returned_as_scripture():
    embedder = FakeEmbedder()
    store = ScriptureStore(QdrantClient(":memory:"), "scriptures", DIM)
    tagged = ScriptureRecord(
        id="t-1", belief_system="Faith-Alpha", source_book="T 1:1", content="Plain words.", themes="quokka marsupial"
    )
    other = ScriptureRecord(id="t-2", belief_system="Faith-Alpha", source_book="T 2:2", content="Other words.")
    ingest([tagged, other], embedder, store, recreate=False)
    match = store.search(embedder.embed("quokka marsupial"), "Faith-Alpha")
    assert match.id == "t-1"
    assert match.content == "Plain words."

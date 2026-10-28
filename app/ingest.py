"""Embed scripture records and load them into the vector store (spec section 3).

    python -m app.ingest data/scriptures.sample.jsonl
    python -m app.ingest my_library.jsonl --recreate

Each line is a JSON object with the fields id, belief_system, source_book and content, and optionally
themes: curated search metadata that is embedded together with the passage but never shown to users.
The passage text is stored exactly as given, so verify it against your source before loading it.
Re-running upserts by id; use --recreate to start from an empty collection (required after changing
the embedding model).
With embedded Qdrant (no QDRANT_URL) stop the API first: the on-disk store allows one process at a time.
"""

import argparse
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from app.config import get_settings
from app.schemas import ScriptureRecord
from app.services.embedding import Embedder, SentenceTransformerEmbedder
from app.services.vector_store import ScriptureStore

BATCH_SIZE = 128


def load_records(path: Path) -> list[ScriptureRecord]:
    records: list[ScriptureRecord] = []
    problems: list[str] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(ScriptureRecord.model_validate_json(line))
        except ValidationError as exc:
            first = exc.errors()[0]
            problems.append(f"line {number}: {first['msg']} at {'.'.join(str(part) for part in first['loc'])}")
    if problems:
        raise ValueError("invalid records:\n  " + "\n  ".join(problems))
    duplicates = sorted(scripture_id for scripture_id, n in Counter(r.id for r in records).items() if n > 1)
    if duplicates:
        raise ValueError(f"duplicate ids: {', '.join(duplicates)}")
    if not records:
        raise ValueError("the file contains no records")
    return records


def ingest(records: Sequence[ScriptureRecord], embedder: Embedder, store: ScriptureStore, *, recreate: bool) -> None:
    store.ensure_collection(recreate=recreate)
    for start in range(0, len(records), BATCH_SIZE):
        batch = records[start : start + BATCH_SIZE]
        store.upsert(batch, embedder.embed_many([record.embedding_text for record in batch]))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Embed scriptures and load them into the vector store.")
    parser.add_argument("file", type=Path, help="JSONL file: one scripture record per line")
    parser.add_argument("--recreate", action="store_true", help="drop the collection first")
    args = parser.parse_args(argv)

    try:
        records = load_records(args.file)
    except (OSError, ValueError) as exc:
        print(f"Cannot load {args.file}: {exc}", file=sys.stderr)
        return 1

    settings = get_settings()
    embedder = SentenceTransformerEmbedder(settings.embedding_model, settings.embedding_dim)
    store = ScriptureStore.from_settings(settings)
    try:
        ingest(records, embedder, store, recreate=args.recreate)
        total = store.count()
    finally:
        store.close()

    tagged = sum(1 for record in records if record.themes)
    print(f"Loaded {len(records)} records ({tagged} with themes). The collection now holds {total}.")
    for belief_system, n in sorted(Counter(r.belief_system for r in records).items()):
        print(f"  {belief_system}: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

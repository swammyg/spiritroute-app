"""Load the expanded multi-tradition scripture library into the vector store.

    .venv/bin/python scripts/ingest_global.py

Converts data/expanded_scriptures.json to the JSONL format expected by app.ingest,
assigns stable ids, and upserts the records without dropping the existing collection.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ingest import main as ingest_main

SOURCE = PROJECT_ROOT / "data" / "expanded_scriptures.json"
OUTPUT = PROJECT_ROOT / "data" / "expanded_scriptures.jsonl"
REQUIRED_FIELDS = {"belief_system", "source_book", "content"}
OPTIONAL_FIELDS = {"id", "themes"}


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _load_records() -> list[dict[str, str]]:
    raw = json.loads(SOURCE.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"{SOURCE} must contain a non-empty JSON array")

    records: list[dict[str, str]] = []
    used_ids: set[str] = set()
    for number, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"item {number} is not an object")
        missing = REQUIRED_FIELDS - item.keys()
        extra = item.keys() - REQUIRED_FIELDS - OPTIONAL_FIELDS
        if missing or extra:
            raise ValueError(f"item {number} has missing={sorted(missing)} extra={sorted(extra)}")
        for field in item:
            if not isinstance(item[field], str) or not item[field].strip():
                raise ValueError(f"item {number} field {field!r} must be a non-empty string")

        if "id" in item:
            record_id = item["id"]
        else:
            base_id = f"{_slug(item['belief_system'])}-{_slug(item['source_book'])}"
            record_id = base_id
            suffix = 2
            while record_id in used_ids:
                record_id = f"{base_id}-{suffix}"
                suffix += 1
        if record_id in used_ids:
            raise ValueError(f"item {number} reuses id {record_id!r}")
        used_ids.add(record_id)
        records.append({**item, "id": record_id})
    return records


def main() -> int:
    try:
        records = _load_records()
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Cannot load {SOURCE}: {exc}", file=sys.stderr)
        return 1

    OUTPUT.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    print(f"Wrote {len(records)} records to {OUTPUT.relative_to(PROJECT_ROOT)}")
    return ingest_main([str(OUTPUT)])


if __name__ == "__main__":
    sys.exit(main())

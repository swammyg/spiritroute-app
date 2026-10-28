"""Integration smoke test for POST /api/v1/resolve-heart against a running server.

Start the API first:
    .venv/bin/uvicorn app.main:app --reload

Then run:
    .venv/bin/python test_backend.py

Override the target with SPIRITROUTE_BASE_URL and the timeout with SPIRITROUTE_TEST_TIMEOUT.
Exits 0 when every case succeeds, 1 otherwise.
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

import httpx

BASE_URL = os.environ.get("SPIRITROUTE_BASE_URL", "http://127.0.0.1:8000")
RESOLVE_HEART_PATH = "/api/v1/resolve-heart"
TIMEOUT_SECONDS = float(os.environ.get("SPIRITROUTE_TEST_TIMEOUT", "120"))

CASES: list[dict[str, Any]] = [
    {
        "label": "Atheist / Secular + Angry + Co-workers + Worth",
        "payload": {
            "belief_system": "Atheist / Secular",
            "user_emotion": "Angry",
            "user_circle": "Co-workers",
            "user_driver": "Worth",
        },
    },
    {
        "label": "Christianity + Sad + Friends + Belonging",
        "payload": {
            "belief_system": "Christianity",
            "user_emotion": "Sad",
            "user_circle": "Friends",
            "user_driver": "Belonging",
        },
    },
    {
        "label": "Islam + Depressed + Family + Safety",
        "payload": {
            "belief_system": "Islam",
            "user_emotion": "Depressed",
            "user_circle": "Family",
            "user_driver": "Safety",
        },
    },
]


def one_line(value: Any) -> str:
    return " ".join(str(value).split())


def describe_error(response: httpx.Response) -> str:
    """Turn FastAPI's `detail` (string or validation-error list) into one readable line."""
    try:
        body = response.json()
    except ValueError:
        return one_line(response.text) or "(empty body)"
    if isinstance(body, dict) and "detail" in body:
        detail = body["detail"]
        if isinstance(detail, list):
            return "; ".join(
                f"{'.'.join(str(part) for part in error.get('loc', []))}: {error.get('msg', '')}"
                for error in detail
                if isinstance(error, dict)
            )
        return one_line(detail)
    return one_line(json.dumps(body, ensure_ascii=False))


def check_server(client: httpx.Client) -> bool:
    try:
        health = client.get("/health")
        health.raise_for_status()
        body = health.json()
        print(f"Server: {one_line(BASE_URL)} -> {body.get('status')} "
              f"({body.get('scriptures')} scriptures, llm_enabled={body.get('llm_enabled')})")
        belief_systems = client.get("/api/v1/belief-systems")
        belief_systems.raise_for_status()
        available = belief_systems.json().get("belief_systems", [])
        print(f"Loaded belief systems: {', '.join(available) or '(none)'}")
        missing = [
            case["payload"]["belief_system"]
            for case in CASES
            if case["payload"]["belief_system"] not in available
        ]
        if missing:
            print(f"Note: not loaded, so expected to return 404: {', '.join(missing)}")
        print()
        return True
    except (httpx.HTTPError, ValueError) as exc:
        print(f"FAIL  Cannot reach the API at {BASE_URL}: {type(exc).__name__}: {exc}")
        print("      Start it with: .venv/bin/uvicorn app.main:app --reload")
        return False


def run_case(client: httpx.Client, index: int, total: int, case: dict[str, Any]) -> bool:
    print(f"[{index}/{total}] {case['label']}")
    started = time.perf_counter()
    try:
        response = client.post(RESOLVE_HEART_PATH, json=case["payload"])
    except httpx.HTTPError as exc:
        print(f"  FAIL  request error after {time.perf_counter() - started:.2f}s: "
              f"{type(exc).__name__}: {exc}\n")
        return False
    elapsed = time.perf_counter() - started

    if response.status_code != 200:
        print(f"  FAIL  HTTP {response.status_code} after {elapsed:.2f}s: {describe_error(response)}\n")
        return False

    try:
        body = response.json()
    except ValueError:
        print(f"  FAIL  HTTP 200 but the body is not JSON: {one_line(response.text)[:200]!r}\n")
        return False

    if body.get("crisis_override") is True:
        print(f"  FAIL  crisis override returned for these answers: {one_line(body.get('message', ''))}\n")
        return False

    source = body.get("source")
    word_of_hope = body.get("word_of_hope")
    if not source or not word_of_hope:
        print(f"  FAIL  response is missing source/word_of_hope: "
              f"{one_line(json.dumps(body, ensure_ascii=False))}\n")
        return False

    print(f"  PASS  HTTP 200 in {elapsed:.2f}s")
    print(f"        source:       {one_line(source)}")
    print(f"        word_of_hope: {one_line(word_of_hope)}\n")
    return True


def main() -> int:
    passed = 0
    with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT_SECONDS) as client:
        if not check_server(client):
            return 1
        for index, case in enumerate(CASES, start=1):
            if run_case(client, index, len(CASES), case):
                passed += 1

    failed = len(CASES) - passed
    print(f"Summary: {passed} passed, {failed} failed, {len(CASES)} total")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

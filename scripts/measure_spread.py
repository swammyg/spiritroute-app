"""Measure how the wizard's 64 answer combinations spread over a belief system's passages.

    python scripts/measure_spread.py http://127.0.0.1:8000 --belief-system Christianity
    python scripts/measure_spread.py http://127.0.0.1:8000 --belief-system Christianity --table \\
        --intended data/scriptures.sample.drivers.json

It calls POST /api/v1/resolve-heart once for every valid combination of emotion, circle and driver and
records which passage comes back. A search that works sends different answers to different passages;
one that has collapsed sends most of them to the same few. Run it after changing themes, the embedding
model or QUERY_CENTERING, and on your own library.

Start the API with LLM_ENABLED=false while measuring. The search does not depend on the LLM, but with it
on, each of the 64 requests would also wait for a generation.

The API returns one passage per answer, so at most 64 distinct passages can ever be shown.

--intended is a JSON object mapping each passage's source (exactly as the API returns it) to the driver
it is meant to serve, e.g. {"Psalms 34:18 (WEB)": "Safety"}. It adds the share of answers whose passage
is meant for the driver that was chosen, which is only as good as your labels.

Standard library only.
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

Answer = tuple[str, str, str]  # (emotion, circle, driver)


@dataclass
class Spread:
    answers: int
    distinct: int
    busiest: str
    busiest_count: int
    circle_changes: int  # emotion+driver cells where the circle changes the passage
    circle_cells: int
    emotion_changes: int  # circle+driver pairs where the emotion changes the passage
    emotion_pairs: int
    emotion_groups: list[str] = field(default_factory=list)
    intended_hits: int | None = None
    intended_total: int | None = None


def collect_picks(options: dict, post: Callable[[dict], dict], belief_system: str) -> dict[Answer, str]:
    """Ask for a passage for every valid answer; `post` sends one resolve-heart body and returns the reply."""
    picks: dict[Answer, str] = {}
    for emotion in options["emotions"]:
        for circle in options["circles"]:
            for driver in options["drivers_by_emotion"][emotion]:
                reply = post(
                    {
                        "belief_system": belief_system,
                        "user_emotion": emotion,
                        "user_circle": circle,
                        "user_driver": driver,
                    }
                )
                if "source" not in reply:
                    raise RuntimeError(f"unexpected reply for {emotion}/{circle}/{driver}: {reply}")
                picks[(emotion, circle, driver)] = reply["source"]
    return picks


def measure(picks: dict[Answer, str], options: dict, intended: dict[str, str] | None = None) -> Spread:
    circles = options["circles"]
    tally = Counter(picks.values())
    busiest, busiest_count = tally.most_common(1)[0]

    cells = {(emotion, driver) for emotion, _, driver in picks}
    circle_changes = sum(
        len({picks[(emotion, circle, driver)] for circle in circles}) > 1 for emotion, driver in cells
    )

    # Emotions that are offered the same drivers can be compared with each other.
    by_drivers: dict[tuple[str, ...], list[str]] = {}
    for emotion, drivers in options["drivers_by_emotion"].items():
        by_drivers.setdefault(tuple(drivers), []).append(emotion)
    comparable = [(drivers, emotions) for drivers, emotions in by_drivers.items() if len(emotions) > 1]
    emotion_pairs = sum(len(circles) * len(drivers) for drivers, _ in comparable)
    emotion_changes = sum(
        len({picks[(emotion, circle, driver)] for emotion in emotions}) > 1
        for drivers, emotions in comparable
        for circle in circles
        for driver in drivers
    )

    spread = Spread(
        answers=len(picks),
        distinct=len(tally),
        busiest=busiest,
        busiest_count=busiest_count,
        circle_changes=circle_changes,
        circle_cells=len(cells),
        emotion_changes=emotion_changes,
        emotion_pairs=emotion_pairs,
        emotion_groups=["/".join(emotions) for _, emotions in comparable],
    )
    if intended is not None:
        labelled = [(source, driver) for (_, _, driver), source in picks.items() if source in intended]
        spread.intended_hits = sum(intended[source] == driver for source, driver in labelled)
        spread.intended_total = len(labelled)
    return spread


def format_report(spread: Spread, belief_system: str, base_url: str) -> list[str]:
    lines = [
        f'Spread of the {spread.answers} wizard answers over "{belief_system}" ({base_url})',
        f"  distinct passages:  {spread.distinct} of {spread.answers} possible",
        f"  busiest passage:    {spread.busiest} ({spread.busiest_count} answers)",
        f"  circle changes the pick in {spread.circle_changes}/{spread.circle_cells} emotion+driver cells",
    ]
    if spread.emotion_pairs:
        groups = "; ".join(spread.emotion_groups)
        lines.append(
            f"  emotion changes the pick in {spread.emotion_changes}/{spread.emotion_pairs} "
            f"circle+driver pairs ({groups})"
        )
    if spread.intended_total is not None:
        note = "" if spread.intended_total == spread.answers else f" (only {spread.intended_total} picks have a label)"
        lines.append(f"  passage is meant for the chosen driver: {spread.intended_hits}/{spread.intended_total}{note}")
    return lines


def format_table(picks: dict[Answer, str], options: dict) -> list[str]:
    circles = options["circles"]
    lines = [f"  {'emotion':<9} {'driver':<10} " + " | ".join(circles)]
    for emotion in sorted(options["emotions"]):
        for driver in sorted(options["drivers_by_emotion"][emotion]):
            row = " | ".join(picks[(emotion, circle, driver)] for circle in circles)
            lines.append(f"  {emotion:<9} {driver:<10} {row}")
    return lines


def request_json(url: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {} if body is None else {"Content-Type": "application/json"}
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"{url} answered {exc.code}: {detail}") from None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Measure how the wizard's 64 answers spread over a belief system's passages."
    )
    parser.add_argument("base_url", help="a running API, e.g. http://127.0.0.1:8000")
    parser.add_argument("--belief-system", required=True, help='as listed by GET /api/v1/belief-systems')
    parser.add_argument("--intended", type=Path, help="JSON file mapping each passage's source to its intended driver")
    parser.add_argument("--table", action="store_true", help="also print the passage chosen for every answer")
    args = parser.parse_args(argv)

    base_url = args.base_url.rstrip("/")
    try:
        intended = None
        if args.intended:
            intended = json.loads(args.intended.read_text(encoding="utf-8"))
            if not isinstance(intended, dict):
                raise ValueError(f"{args.intended} must contain a JSON object")
        options = request_json(f"{base_url}/api/v1/diagnostic-options")
        picks = collect_picks(
            options, lambda body: request_json(f"{base_url}/api/v1/resolve-heart", body), args.belief_system
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Cannot measure: {exc}", file=sys.stderr)
        return 1

    print("\n".join(format_report(measure(picks, options, intended), args.belief_system, base_url)))
    if args.table:
        print("\n" + "\n".join(format_table(picks, options)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

import importlib.util
import socket
from pathlib import Path

import pytest

from app.schemas import Driver
from tests.fakes import ALPHA_FAR, ALPHA_NEAR

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("measure_spread", ROOT / "scripts" / "measure_spread.py")
measure_spread = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(measure_spread)

URL = "/api/v1/resolve-heart"


@pytest.fixture
def options(make_client):
    return make_client().get("/api/v1/diagnostic-options").json()


def picks_where(options, source_for):
    return {
        (emotion, circle, driver): source_for(emotion, circle, driver)
        for emotion in options["emotions"]
        for circle in options["circles"]
        for driver in options["drivers_by_emotion"][emotion]
    }


# --- the numbers --------------------------------------------------------------------------------


def test_one_passage_for_every_answer_is_a_collapsed_search(options):
    spread = measure_spread.measure(picks_where(options, lambda e, c, d: "Only 1:1"), options)
    assert (spread.answers, spread.distinct) == (64, 1)
    assert (spread.busiest, spread.busiest_count) == ("Only 1:1", 64)
    assert (spread.circle_changes, spread.circle_cells) == (0, 16)
    assert (spread.emotion_changes, spread.emotion_pairs) == (0, 16)
    assert spread.emotion_groups == ["Depressed/Sad/Angry"]


def test_circle_alone_choosing_the_passage(options):
    spread = measure_spread.measure(picks_where(options, lambda e, c, d: f"for {c}"), options)
    assert spread.distinct == 4
    assert (spread.circle_changes, spread.circle_cells) == (16, 16)
    assert spread.emotion_changes == 0


def test_emotion_alone_choosing_the_passage(options):
    spread = measure_spread.measure(picks_where(options, lambda e, c, d: f"for {e}"), options)
    assert spread.distinct == 4
    assert spread.circle_changes == 0
    assert (spread.emotion_changes, spread.emotion_pairs) == (16, 16)


def test_every_answer_with_its_own_passage(options):
    spread = measure_spread.measure(picks_where(options, lambda e, c, d: f"{e}/{c}/{d}"), options)
    assert (spread.distinct, spread.busiest_count) == (64, 1)


def test_intended_share_counts_only_labelled_picks(options):
    picks = picks_where(options, lambda e, c, d: "Unlabelled 9:9" if d == "Worth" else f"{d} passage")
    intended = {f"{driver.value} passage": driver.value for driver in Driver}
    intended["Safety passage"] = "Worth"  # a wrong label, so every Safety answer is a miss
    spread = measure_spread.measure(picks, options, intended)
    # 12 Worth answers are unlabelled and left out; 12 Safety answers are labelled wrongly.
    assert (spread.intended_hits, spread.intended_total) == (40, 52)


def test_report_lists_the_headline_numbers(options):
    spread = measure_spread.measure(picks_where(options, lambda e, c, d: f"for {e}"), options)
    text = "\n".join(measure_spread.format_report(spread, "Faith-Alpha", "http://api.test"))
    assert 'over "Faith-Alpha" (http://api.test)' in text
    assert "distinct passages:  4 of 64 possible" in text
    assert "emotion changes the pick in 16/16 circle+driver pairs (Depressed/Sad/Angry)" in text
    assert "meant for" not in text  # no labels were given


def test_table_has_a_row_for_every_emotion_and_driver(options):
    lines = measure_spread.format_table(picks_where(options, lambda e, c, d: f"{e}-{c}-{d}"), options)
    assert len(lines) == 1 + 16
    row = next(line for line in lines if line.split()[:2] == ["Sad", "Belonging"])
    assert row.endswith(
        "Sad-Family-Belonging | Sad-Friends-Belonging | Sad-Co-workers-Belonging | Sad-Finances-Belonging"
    )


# --- talking to the API -------------------------------------------------------------------------


def test_collecting_picks_from_the_real_app_respects_the_belief_system(make_client, options):
    client = make_client()
    picks = measure_spread.collect_picks(options, lambda body: client.post(URL, json=body).json(), "Faith-Alpha")
    assert len(picks) == 64
    assert set(picks.values()) <= {ALPHA_NEAR.source_book, ALPHA_FAR.source_book}


def test_a_reply_without_a_passage_is_an_error(options):
    with pytest.raises(RuntimeError, match="unexpected reply"):
        measure_spread.collect_picks(options, lambda body: {"crisis_override": True}, "Faith-Alpha")


def test_main_reports_an_unreachable_server(capsys):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]  # nothing listens here once the probe closes
    assert measure_spread.main([f"http://127.0.0.1:{port}", "--belief-system", "Faith-Alpha"]) == 1
    assert "Cannot measure" in capsys.readouterr().err


def test_main_rejects_an_intended_file_that_is_not_an_object(tmp_path, capsys):
    labels = tmp_path / "labels.json"
    labels.write_text("[]", encoding="utf-8")
    argv = ["http://127.0.0.1:1", "--belief-system", "Faith-Alpha", "--intended", str(labels)]
    assert measure_spread.main(argv) == 1
    assert "must contain a JSON object" in capsys.readouterr().err

import logging

import pytest

from app.config import Settings
from app.schemas import Driver, Emotion, ScriptureRecord
from app.services.query_vectors import QueryVectors
from tests.fakes import (
    ALPHA_FAR,
    ALPHA_NEAR,
    BETA_EXACT,
    FailingStore,
    FakeLLM,
    RecordingEmbedder,
    SpyStore,
    llm_reply,
    make_store,
)

URL = "/api/v1/resolve-heart"

CRISIS_PAYLOAD = {
    "crisis_override": True,
    "message": (
        "You are incredibly valuable, and you don't have to carry this heavy weight alone. "
        "Please reach out to someone who can stand with you right now."
    ),
    "resources": [
        {"name": "Suicide and crisis hotline", "contact": "Available 24/7 / Free / Confidential"},
        {"name": "Crisis Text Line", "contact": "Text HOME to 741741"},
    ],
}


def body(**overrides) -> dict:
    base = {
        "belief_system": "Faith-Alpha",
        "user_emotion": "Sad",
        "user_circle": "Family",
        "user_driver": "Belonging",
    }
    return {**base, **overrides}


# --- wizard support endpoints -------------------------------------------------------------------


def test_diagnostic_options_describe_the_wizard(make_client):
    data = make_client().get("/api/v1/diagnostic-options").json()
    assert data["emotions"] == ["Depressed", "Sad", "Happy", "Angry"]
    assert data["circles"] == ["Family", "Friends", "Co-workers", "Finances"]
    assert data["drivers_by_emotion"] == {
        "Depressed": ["Safety", "Worth", "Autonomy", "Belonging"],
        "Sad": ["Safety", "Worth", "Autonomy", "Belonging"],
        "Angry": ["Safety", "Worth", "Autonomy", "Belonging"],
        "Happy": ["Gratitude", "Connection", "Purpose", "Abundance"],
    }


def test_belief_systems_lists_whatever_is_loaded(make_client):
    assert make_client().get("/api/v1/belief-systems").json() == {"belief_systems": ["Faith-Alpha", "Faith-Beta"]}


def test_health(make_client):
    assert make_client().get("/health").json() == {"status": "ok", "scriptures": 3, "llm_enabled": False}


# --- resolve-heart ------------------------------------------------------------------------------


def test_returns_database_scripture_with_the_llms_commentary(make_client):
    llm = FakeLLM(llm_reply("A word of hope.", "A short prayer."))
    response = make_client(llm).post(URL, json=body())
    assert response.status_code == 200
    assert response.json() == {
        "crisis_override": False,
        "source": ALPHA_NEAR.source_book,
        "scripture_text": ALPHA_NEAR.content,
        "word_of_hope": "A word of hope.",
        "prayer_reflection": "A short prayer.",
    }


def test_belief_system_is_a_hard_filter(make_client):
    client = make_client()
    # Faith-Beta's passage is the closest match in the whole collection, but must never be shown to Faith-Alpha.
    alpha = client.post(URL, json=body(belief_system="Faith-Alpha")).json()
    beta = client.post(URL, json=body(belief_system="Faith-Beta")).json()
    assert alpha["scripture_text"] == ALPHA_NEAR.content
    assert beta["scripture_text"] == BETA_EXACT.content


def test_happy_path_searches_with_its_own_query(make_client):
    response = make_client().post(
        URL, json=body(user_emotion="Happy", user_circle="Friends", user_driver="Gratitude")
    )
    assert response.status_code == 200
    assert response.json()["scripture_text"] == ALPHA_FAR.content


@pytest.mark.parametrize(
    ("emotion", "driver"),
    [("Angry", "Autonomy"), ("Depressed", "Safety"), ("Happy", "Gratitude"), ("Happy", "Abundance")],
)
def test_finances_circle_accepts_the_drivers_offered_for_the_emotion(make_client, emotion, driver):
    payload = body(user_emotion=emotion, user_circle="Finances", user_driver=driver)
    assert make_client().post(URL, json=payload).status_code == 200


def test_unknown_belief_system_is_404(make_client):
    response = make_client().post(URL, json=body(belief_system="Faith-Gamma"))
    assert response.status_code == 404
    assert response.json() == {"detail": "No matching scripture found"}


def test_belief_system_match_is_exact(make_client):
    assert make_client().post(URL, json=body(belief_system="faith-alpha")).status_code == 404


@pytest.mark.parametrize(
    ("emotion", "driver"),
    [("Sad", "Gratitude"), ("Angry", "Purpose"), ("Depressed", "Abundance"), ("Happy", "Safety"), ("Happy", "Worth")],
)
def test_driver_must_belong_to_the_emotions_group(make_client, emotion, driver):
    response = make_client().post(URL, json=body(user_emotion=emotion, user_driver=driver))
    assert response.status_code == 422
    assert "user_driver" in response.json()["detail"]


@pytest.mark.parametrize(
    "payload",
    [
        body(user_emotion="Joyful"),
        body(user_circle="Pets"),
        body(user_driver="Money"),
        body(belief_system=""),
        {k: v for k, v in body().items() if k != "user_circle"},
        body(free_text="x" * 1001),
    ],
    ids=["emotion", "circle", "driver", "empty-belief", "missing-field", "free-text-too-long"],
)
def test_invalid_payloads_are_422(make_client, payload):
    assert make_client().post(URL, json=payload).status_code == 422


def test_database_failure_is_a_500_with_the_specs_message(make_client):
    response = make_client(store=FailingStore()).post(URL, json=body())
    assert response.status_code == 500
    assert response.json() == {"detail": "Database lookup failure"}


# --- zero scripture hallucination ---------------------------------------------------------------


def test_an_invented_quote_from_the_llm_never_reaches_the_client(make_client):
    llm = FakeLLM(llm_reply('The text says "love conquers every fear and heals every wound forever".', "Peace."))
    response = make_client(llm).post(URL, json=body())
    assert response.status_code == 200
    assert response.json()["scripture_text"] == ALPHA_NEAR.content
    assert "love conquers" not in response.text
    assert len(llm.calls) == 2  # retried once, then used the fallback template


def test_the_llm_cannot_replace_the_scripture_text(make_client):
    raw = '{"word_of_hope": "Hope.", "prayer_reflection": "Peace.", "scripture_text": "INVENTED", "source": "FAKE 1:1"}'
    data = make_client(FakeLLM(raw)).post(URL, json=body()).json()
    assert data["scripture_text"] == ALPHA_NEAR.content
    assert data["source"] == ALPHA_NEAR.source_book


def test_llm_outage_still_returns_the_verified_scripture(make_client):
    from app.services.llm_client import LLMUnavailable

    response = make_client(FakeLLM(LLMUnavailable("connection refused"))).post(URL, json=body())
    data = response.json()
    assert response.status_code == 200
    assert data["scripture_text"] == ALPHA_NEAR.content
    assert data["word_of_hope"] and data["prayer_reflection"]
    assert "Faith-Alpha" in data["prayer_reflection"]


def test_without_an_llm_the_fallback_template_is_used(make_client):
    data = make_client(None).post(URL, json=body()).json()
    assert data["scripture_text"] == ALPHA_NEAR.content
    assert data["word_of_hope"] and data["prayer_reflection"]


# --- crisis override ----------------------------------------------------------------------------


def test_crisis_text_returns_the_override_and_touches_nothing_else(make_client):
    recording = RecordingEmbedder()
    store = SpyStore(make_store(recording))
    llm = FakeLLM(llm_reply())
    client = make_client(llm, store=store, queries=QueryVectors(recording, center_queries=True))
    embedded_at_startup = len(recording.texts)
    response = client.post(URL, json=body(free_text="I want to end my life"))
    assert response.status_code == 200
    assert response.json() == CRISIS_PAYLOAD
    assert len(recording.texts) == embedded_at_startup
    assert store.searches == 0
    assert llm.calls == []


def test_crisis_override_wins_over_validation_errors(make_client):
    response = make_client().post(URL, json=body(user_driver="Gratitude", free_text="I don't want to live anymore"))
    assert response.status_code == 200
    assert response.json() == CRISIS_PAYLOAD


def test_configured_selection_triggers_the_override(make_client, embedder):
    settings = Settings(_env_file=None, crisis_selection_triggers=[(Emotion.SAD, Driver.WORTH)])
    client = make_client(settings=settings)
    assert client.post(URL, json=body(user_driver="Worth")).json() == CRISIS_PAYLOAD
    assert client.post(URL, json=body(user_driver="Safety")).json()["crisis_override"] is False


def test_ordinary_free_text_does_not_trigger_the_override(make_client):
    data = make_client().post(URL, json=body(free_text="My brother never listens to me")).json()
    assert data["crisis_override"] is False


# --- privacy ------------------------------------------------------------------------------------


def test_responses_are_not_cacheable(make_client):
    client = make_client()
    assert client.post(URL, json=body()).headers["cache-control"] == "no-store"
    assert client.get("/health").headers["cache-control"] == "no-store"


def test_free_text_is_never_logged_searched_prompted_or_echoed(make_client, caplog):
    marker = "zq-private-marker-7781"
    recording = RecordingEmbedder()
    llm = FakeLLM(llm_reply())
    client = make_client(llm, store=make_store(recording), queries=QueryVectors(recording, center_queries=True))
    with caplog.at_level(logging.DEBUG):
        ordinary = client.post(URL, json=body(free_text=f"my coworker is unkind {marker}"))
        crisis = client.post(URL, json=body(free_text=f"I want to kill myself {marker}"))
    assert ordinary.status_code == 200
    assert crisis.json()["crisis_override"] is True
    assert marker not in caplog.text
    assert marker not in ordinary.text
    assert marker not in crisis.text
    assert not any(marker in text for text in recording.texts)
    assert not any(marker in system or marker in user for system, user in llm.calls)


# --- themes -------------------------------------------------------------------------------------


def test_themes_steer_the_search_but_are_never_shown_or_prompted(make_client, embedder):
    # Without its themes, "Rivers and hills." shares no words with the search query and would lose to the
    # plain passage, which shares two.
    themes = "feeling sad family belonging lack issue"
    plain = ScriptureRecord(id="p-1", belief_system="Faith-Alpha", source_book="Plain 1:1", content="A sad hill.")
    tagged = ScriptureRecord(
        id="p-2", belief_system="Faith-Alpha", source_book="Tagged 2:2", content="Rivers and hills.", themes=themes
    )
    llm = FakeLLM(llm_reply())
    response = make_client(llm, store=make_store(embedder, records=[plain, tagged])).post(URL, json=body())
    assert response.json()["scripture_text"] == "Rivers and hills."
    assert themes not in response.text
    assert themes not in llm.calls[0][0]

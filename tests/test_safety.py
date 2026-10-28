import pytest

from app.schemas import Circle, Driver, Emotion, ResolveHeartRequest
from app.services.safety import crisis_response, mentions_self_harm, needs_crisis_override


def request(free_text=None, emotion=Emotion.SAD, driver=Driver.WORTH) -> ResolveHeartRequest:
    return ResolveHeartRequest(
        belief_system="Faith-Alpha",
        user_emotion=emotion,
        user_circle=Circle.FAMILY,
        user_driver=driver,
        free_text=free_text,
    )


@pytest.mark.parametrize(
    "text",
    [
        "I want to kill myself",
        "i've been feeling suicidal lately",
        "I DON'T WANT TO LIVE ANYMORE",
        "i dont want to be here any more",
        "Sometimes I think everyone would be better off without me",
        "thinking of ending my life",
        "I want to take my own life",
        "I just want to end it all",
        "I keep wanting to hurt myself",
        "i have started cutting myself",
        "self-harm",
        "I wish I was dead",
        "I wish I could just die",
        "there is no point in living",
        "I'm going to jump off a bridge",
        "kms",
        "I don’t want to live",  # curly apostrophe, as typed on a phone keyboard
        "I want\nto   die",  # odd whitespace
    ],
)
def test_explicit_self_harm_language_is_caught(text):
    assert mentions_self_harm(text)
    assert needs_crisis_override(request(free_text=text))


@pytest.mark.parametrize(
    "text",
    [
        "I'm dying to see my friends again",
        "My coworker killed my project and I am furious",
        "Please pray for my grandmother who is dying",
        "I want to end this argument with my brother",
        "I feel overlooked at work",
        "My family never listens to me",
        "I am so grateful today",
        "",
    ],
)
def test_ordinary_distress_is_not_flagged(text):
    assert not mentions_self_harm(text)
    assert not needs_crisis_override(request(free_text=text))


def test_no_free_text_is_not_a_crisis():
    assert not needs_crisis_override(request(free_text=None))


def test_configured_selection_triggers_override_on_their_own():
    triggers = [(Emotion.DEPRESSED, Driver.WORTH)]
    assert needs_crisis_override(request(emotion=Emotion.DEPRESSED, driver=Driver.WORTH), triggers)
    assert not needs_crisis_override(request(emotion=Emotion.DEPRESSED, driver=Driver.SAFETY), triggers)
    assert not needs_crisis_override(request(emotion=Emotion.DEPRESSED, driver=Driver.WORTH))  # none by default


def test_crisis_payload_is_exactly_the_specs():
    assert crisis_response().model_dump() == {
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

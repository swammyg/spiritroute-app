"""Crisis screening and the override payload (spec section 7).

This is a coarse first-line screen: it looks for explicit self-harm language in the optional
`free_text` field, plus any wizard answers the operator has configured as high risk. It is
English-only and keyword based, so it will miss indirect phrasing. Have a clinical advisor review
the patterns and the resources below before this ships.
"""

import re
import unicodedata
from collections.abc import Collection

from app.schemas import CrisisResource, CrisisResponse, Driver, Emotion, ResolveHeartRequest

CRISIS_MESSAGE = (
    "You are incredibly valuable, and you don't have to carry this heavy weight alone. "
    "Please reach out to someone who can stand with you right now."
)
CRISIS_RESOURCES = (
    CrisisResource(name="Suicide and crisis hotline", contact="Available 24/7 / Free / Confidential"),
    CrisisResource(name="Crisis Text Line", contact="Text HOME to 741741"),
)

_SELF_HARM_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        r"\bsuicid(?:e|al)\b",
        r"\bkms\b",
        r"\bkill(?:ing)? my ?self\b",
        r"\bun-?aliv(?:e|ing)\b",
        r"\b(?:end|ending|take|taking) my (?:own )?life\b",
        r"\bwant(?:ed|s|ing)? to die\b",
        r"\b(?:wanna|ready to) die\b",
        r"\bwish (?:that )?i (?:was|were) (?:dead|never born)\b",
        r"\bwish (?:that )?i (?:could |would )?(?:just )?(?:die|not wake up|never wake up)\b",
        r"\bbetter off (?:dead|without me)\b",
        r"\b(?:don'?t|do not) want to (?:live|be alive|be here|exist)(?: any ?more)?\b",
        r"\bno (?:reason|point) (?:in |to )?(?:living|live|going on|being alive)\b",
        r"\bcan'?t go on living\b",
        r"\bend it all\b",
        r"\bself[- ]?harm(?:ing)?\b",
        r"\b(?:hurt|hurting|harm|harming|cut|cutting|injure|injuring) my ?self\b",
        r"\b(?:hang|hanging|shoot|shooting|drown|drowning|poison|poisoning|stab|stabbing|starve|starving) my ?self\b",
        r"\bjump(?:ing)? (?:off|from) (?:a |the )?(?:bridge|building|roof|cliff|balcony)\b",
        r"\bover ?dos(?:e|ed|ing)\b",
    )
)


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = text.replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", text)


def mentions_self_harm(text: str) -> bool:
    normalized = _normalize(text)
    return any(pattern.search(normalized) for pattern in _SELF_HARM_PATTERNS)


def needs_crisis_override(
    request: ResolveHeartRequest,
    selection_triggers: Collection[tuple[Emotion, Driver]] = (),
) -> bool:
    if (request.user_emotion, request.user_driver) in selection_triggers:
        return True
    return bool(request.free_text) and mentions_self_harm(request.free_text)


def crisis_response() -> CrisisResponse:
    return CrisisResponse(message=CRISIS_MESSAGE, resources=list(CRISIS_RESOURCES))

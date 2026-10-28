"""Word of Hope and Prayer/Reflection generation (spec section 6).

The LLM writes only these two commentary fields. The scripture text returned to the client is read
from the database by the route and is never taken from model output.
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.schemas import Circle, Driver, Emotion
from app.services.llm_client import LLMClient, LLMUnavailable
from app.services.output_guard import ReflectionRejected, check_reflection

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = (Path(__file__).resolve().parent.parent / "prompts" / "system_prompt.txt").read_text(
    encoding="utf-8"
)
_PLACEHOLDER = re.compile(
    r"\{(user_emotion|user_circle|user_driver|belief_system|database_source_book|database_scripture_text)\}"
)
_USER_PROMPT = "Write the Word of Hope and the Personalized Prayer/Reflection now. Reply with the JSON object only."


@dataclass(frozen=True)
class ReflectionContext:
    emotion: Emotion
    circle: Circle
    driver: Driver
    belief_system: str
    source_book: str
    scripture_text: str


class Reflection(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    word_of_hope: str = Field(min_length=1)
    prayer_reflection: str = Field(min_length=1)

    @field_validator("word_of_hope", "prayer_reflection", mode="before")
    @classmethod
    def _join_lines(cls, value: object) -> object:
        # Small models sometimes return the 3-4 prayer lines as a JSON list instead of one string.
        if isinstance(value, list) and all(isinstance(line, str) for line in value):
            return "\n".join(value)
        return value


def render_system_prompt(ctx: ReflectionContext) -> str:
    """The spec's system prompt with its placeholders filled. Substitution is a single pass, so text
    inside a substituted value (e.g. the scripture) is never re-interpreted as a placeholder."""
    values = {
        "user_emotion": ctx.emotion.value,
        "user_circle": ctx.circle.value,
        "user_driver": ctx.driver.value,
        "belief_system": ctx.belief_system,
        "database_source_book": ctx.source_book,
        "database_scripture_text": ctx.scripture_text,
    }
    return _PLACEHOLDER.sub(lambda match: values[match.group(1)], _PROMPT_TEMPLATE)


class ReflectionService:
    """Asks the LLM, validates what comes back, and falls back to a fixed template if it cannot."""

    def __init__(self, llm: LLMClient | None, *, max_attempts: int, max_words: int) -> None:
        self._llm = llm
        self._max_attempts = max_attempts
        self._max_words = max_words

    async def reflect(self, ctx: ReflectionContext) -> Reflection:
        if self._llm is not None:
            system_prompt = render_system_prompt(ctx)
            for attempt in range(1, self._max_attempts + 1):
                try:
                    raw = await self._llm.complete(system_prompt, _USER_PROMPT)
                    reflection = Reflection.model_validate_json(raw)
                    check_reflection(
                        (reflection.word_of_hope, reflection.prayer_reflection),
                        source_book=ctx.source_book,
                        scripture_text=ctx.scripture_text,
                        max_words=self._max_words,
                    )
                    return reflection
                except LLMUnavailable as exc:
                    logger.warning("LLM unavailable, using fallback reflection: %s", exc)
                    break
                except ValidationError:
                    logger.warning("LLM output was not the expected JSON (attempt %d/%d)", attempt, self._max_attempts)
                except ReflectionRejected as exc:
                    logger.warning("LLM output rejected (attempt %d/%d): %s", attempt, self._max_attempts, exc)
            else:
                logger.warning("LLM output rejected on every attempt, using fallback reflection")
        return fallback_reflection(ctx)

    async def aclose(self) -> None:
        if self._llm is not None:
            await self._llm.aclose()


# --- Fixed-template fallback -------------------------------------------------------------------
# Used when the LLM is disabled, down, or keeps failing validation. Contains no scripture.

_HARDSHIP_STRUGGLE = {  # "...make it hard to {x}"
    Driver.SAFETY: "feel safe",
    Driver.WORTH: "feel valued",
    Driver.AUTONOMY: "have a say",
    Driver.BELONGING: "feel that you belong",
}
_HARDSHIP_PRAYER = {  # "May I find {x}."
    Driver.SAFETY: "safety and shelter",
    Driver.WORTH: "a deep sense of my own worth",
    Driver.AUTONOMY: "the strength to set healthy boundaries",
    Driver.BELONGING: "a place where I belong",
}
_JOY_GIFT = {  # "May {x} keep growing in you."
    Driver.GRATITUDE: "a thankful heart",
    Driver.CONNECTION: "deep and lasting connection",
    Driver.PURPOSE: "a clear sense of purpose",
    Driver.ABUNDANCE: "a generous, contented spirit",
}
_HEART = {Emotion.DEPRESSED: "heavy", Emotion.SAD: "sorrowful", Emotion.ANGRY: "angry"}


def fallback_reflection(ctx: ReflectionContext) -> Reflection:
    circle = ctx.circle.value.lower()
    if ctx.emotion is Emotion.HAPPY:
        gift = _JOY_GIFT[ctx.driver]
        return Reflection(
            word_of_hope=(
                f"What a gift to feel happy about your {circle}. May {gift} keep growing in you, "
                f"and may {ctx.source_book} help you hold this joy with open hands."
            ),
            prayer_reflection=(
                f"In the spirit of {ctx.belief_system}, I pause with a full heart.\n"
                f"I am thankful for my {circle} and for this moment of joy.\n"
                f"May I grow in {gift}.\n"
                "Let this gladness overflow to those around me."
            ),
        )
    return Reflection(
        word_of_hope=(
            f"It makes sense to feel {ctx.emotion.value.lower()} when things with your {circle} "
            f"make it hard to {_HARDSHIP_STRUGGLE[ctx.driver]}. {ctx.source_book} is offered here as a "
            "steady word for this moment. You are seen, and you do not have to carry this alone."
        ),
        prayer_reflection=(
            f"In the spirit of {ctx.belief_system}, I pause and breathe.\n"
            f"I bring my {_HEART[ctx.emotion]} heart and my {circle} into this moment.\n"
            f"May I find {_HARDSHIP_PRAYER[ctx.driver]}.\n"
            "Let peace settle where there has been turmoil."
        ),
    )

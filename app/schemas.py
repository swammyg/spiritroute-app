"""Request and response contracts for the SpiritRoute API (spec sections 3, 4, 6 and 7)."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Emotion(str, Enum):
    """Step 1: primary emotion."""

    DEPRESSED = "Depressed"
    SAD = "Sad"
    HAPPY = "Happy"
    ANGRY = "Angry"


class Circle(str, Enum):
    """Step 2: relational circle."""

    FAMILY = "Family"
    FRIENDS = "Friends"
    CO_WORKERS = "Co-workers"
    FINANCES = "Finances"


class Driver(str, Enum):
    """Step 3: core psychological driver. Which four are offered depends on the Step 1 emotion."""

    SAFETY = "Safety"
    WORTH = "Worth"
    AUTONOMY = "Autonomy"
    BELONGING = "Belonging"
    GRATITUDE = "Gratitude"
    CONNECTION = "Connection"
    PURPOSE = "Purpose"
    ABUNDANCE = "Abundance"


class ResolveHeartRequest(BaseModel):
    """The three wizard answers plus the user's belief profile."""

    model_config = ConfigDict(str_strip_whitespace=True)

    belief_system: str = Field(
        min_length=1,
        max_length=64,
        description="Hard filter: only scriptures from this belief system are searched. "
        "Must match a value from GET /api/v1/belief-systems exactly.",
        examples=["Christianity"],
    )
    user_emotion: Emotion
    user_circle: Circle
    user_driver: Driver = Field(
        description="Depressed/Sad/Angry: Safety, Worth, Autonomy or Belonging. "
        "Happy: Gratitude, Connection, Purpose or Abundance."
    )
    free_text: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional. Screened for self-harm risk (spec section 7) and then discarded: "
        "it is never searched, sent to the LLM, stored or logged.",
    )


class ScriptureResponse(BaseModel):
    crisis_override: Literal[False] = False
    source: str = Field(description="Reference of the verified passage, e.g. 'Psalms 34:18 (WEB)'.")
    scripture_text: str = Field(description="Verbatim text from the database. Never written by the LLM.")
    word_of_hope: str
    prayer_reflection: str


class CrisisResource(BaseModel):
    name: str
    contact: str


class CrisisResponse(BaseModel):
    crisis_override: Literal[True] = True
    message: str
    resources: list[CrisisResource]


class DiagnosticOptions(BaseModel):
    """Everything the 3-step wizard needs to render itself."""

    emotions: list[Emotion]
    circles: list[Circle]
    drivers_by_emotion: dict[Emotion, list[Driver]]


class BeliefSystems(BaseModel):
    belief_systems: list[str]


class Health(BaseModel):
    status: Literal["ok"]
    scriptures: int
    llm_enabled: bool


class ScriptureRecord(BaseModel):
    """One row of the `scriptures` collection (spec section 3). The embedding is computed at ingest time."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=1, examples=["bible-psalm-147-3"])
    belief_system: str = Field(min_length=1, examples=["Christianity"])
    source_book: str = Field(min_length=1, examples=["Psalms 147:3 (WEB)"])
    content: str = Field(min_length=1, description="The static, verified text, stored and returned verbatim.")
    themes: str | None = Field(
        default=None,
        description="Optional curated search metadata: the feelings, needs and relationships this passage "
        "speaks to, in everyday words. Embedded together with the passage so the search can find it. "
        "Never shown to users and never sent to the LLM.",
        examples=["grief and a broken heart, sadness, healing, being cared for"],
    )

    @field_validator("themes")
    @classmethod
    def _blank_themes_mean_none(cls, value: str | None) -> str | None:
        return value or None

    @property
    def embedding_text(self) -> str:
        """What gets embedded. Themes come first, so a very long passage can only truncate itself."""
        return f"Themes: {self.themes}\n\n{self.content}" if self.themes else self.content

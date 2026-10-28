"""The 3-question diagnostic (spec section 4) and the search query built from its answers (spec section 5)."""

from app.schemas import Circle, Driver, Emotion

HARDSHIP_DRIVERS = (Driver.SAFETY, Driver.WORTH, Driver.AUTONOMY, Driver.BELONGING)
HAPPY_DRIVERS = (Driver.GRATITUDE, Driver.CONNECTION, Driver.PURPOSE, Driver.ABUNDANCE)


def drivers_for(emotion: Emotion) -> tuple[Driver, ...]:
    """The Step 3 options offered for a Step 1 answer."""
    return HAPPY_DRIVERS if emotion is Emotion.HAPPY else HARDSHIP_DRIVERS


def all_answers() -> list[tuple[Emotion, Circle, Driver]]:
    """Every valid combination of wizard answers: 4 emotions x 4 circles x 4 drivers = 64."""
    return [(emotion, circle, driver) for emotion in Emotion for circle in Circle for driver in drivers_for(emotion)]


def driver_error(emotion: Emotion, driver: Driver) -> str | None:
    """Why `driver` is not a valid Step 3 answer for `emotion`, or None if it is valid."""
    allowed = drivers_for(emotion)
    if driver in allowed:
        return None
    return (
        f"user_driver '{driver.value}' is not valid when user_emotion is '{emotion.value}'; "
        f"expected one of: {', '.join(driver.value for driver in allowed)}"
    )


def build_search_query(emotion: Emotion, circle: Circle, driver: Driver) -> str:
    """Sentence that gets embedded and matched against the scripture vectors.

    Depressed/Sad/Angry use the spec's template verbatim. Happy cannot: its drivers (Gratitude,
    Connection, Purpose, Abundance) are strengths, and "an issue ... involving a lack of Gratitude"
    would retrieve passages about ingratitude for someone who is feeling joyful.
    """
    if emotion is Emotion.HAPPY:
        return f"Feeling {emotion.value} about my {circle.value}, and wanting to grow in {driver.value}."
    return f"Feeling {emotion.value} because of an issue with my {circle.value} involving a lack of {driver.value}."

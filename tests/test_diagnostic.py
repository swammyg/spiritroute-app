import pytest

from app.diagnostic import all_answers, build_search_query, driver_error, drivers_for
from app.schemas import Circle, Driver, Emotion


@pytest.mark.parametrize("emotion", [Emotion.DEPRESSED, Emotion.SAD, Emotion.ANGRY])
def test_hardship_emotions_offer_the_four_hardship_drivers(emotion):
    assert drivers_for(emotion) == (Driver.SAFETY, Driver.WORTH, Driver.AUTONOMY, Driver.BELONGING)


def test_happy_offers_the_four_happy_drivers():
    assert drivers_for(Emotion.HAPPY) == (Driver.GRATITUDE, Driver.CONNECTION, Driver.PURPOSE, Driver.ABUNDANCE)


def test_every_driver_is_reachable_from_some_emotion():
    offered = {driver for emotion in Emotion for driver in drivers_for(emotion)}
    assert offered == set(Driver)


@pytest.mark.parametrize(
    ("emotion", "driver"),
    [
        (Emotion.SAD, Driver.GRATITUDE),
        (Emotion.ANGRY, Driver.PURPOSE),
        (Emotion.DEPRESSED, Driver.ABUNDANCE),
        (Emotion.HAPPY, Driver.SAFETY),
        (Emotion.HAPPY, Driver.BELONGING),
    ],
)
def test_driver_from_the_wrong_group_is_an_error(emotion, driver):
    assert driver_error(emotion, driver) is not None


def test_matching_driver_is_not_an_error():
    assert driver_error(Emotion.SAD, Driver.WORTH) is None
    assert driver_error(Emotion.HAPPY, Driver.PURPOSE) is None


def test_hardship_query_is_the_specs_template_verbatim():
    query = build_search_query(Emotion.SAD, Circle.FAMILY, Driver.BELONGING)
    assert query == "Feeling Sad because of an issue with my Family involving a lack of Belonging."


def test_happy_query_does_not_say_lack():
    query = build_search_query(Emotion.HAPPY, Circle.CO_WORKERS, Driver.PURPOSE)
    assert query == "Feeling Happy about my Co-workers, and wanting to grow in Purpose."
    assert "lack" not in query


def test_all_answers_are_the_64_valid_combinations():
    answers = all_answers()
    assert len(answers) == 64
    assert len(set(answers)) == 64
    assert all(driver_error(emotion, driver) is None for emotion, _, driver in answers)

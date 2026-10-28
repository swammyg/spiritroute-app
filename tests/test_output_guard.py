import pytest

from app.services.output_guard import ReflectionRejected, check_reflection

SOURCE = "Psalms 34:18 (WEB)"
VERSE = "Yahweh is near to those who have a broken heart, and saves those who have a crushed spirit."


def check(*texts: str, max_words: int = 150) -> None:
    check_reflection(texts, source_book=SOURCE, scripture_text=VERSE, max_words=max_words)


def test_plain_commentary_passes():
    check("This verse reminds you that you are not alone.", "May I find peace.")


def test_mentioning_the_verified_source_passes():
    check("Psalms 34:18 speaks to a heavy heart.")
    check("Psalms 34 : 18 speaks to a heavy heart.")  # spacing around the colon does not hide a match


def test_citing_a_different_verse_is_rejected():
    with pytest.raises(ReflectionRejected, match="verse numbers"):
        check("As Psalm 23:4 says, you will fear no evil.")


def test_citing_a_verse_in_the_prayer_is_rejected():
    with pytest.raises(ReflectionRejected, match="verse numbers"):
        check("A kind word.", "Remind me of John 3:16.")


def test_quoting_the_verified_text_exactly_passes():
    check('The words "is near to those who have a broken heart" are meant for you.')
    check("The words “saves those who have a crushed spirit” are meant for you.")


def test_quoting_ignores_case_and_punctuation():
    check('As it says, "YAHWEH is near, to those who have a broken heart!"')


def test_quoting_text_that_is_not_in_the_verse_is_rejected():
    with pytest.raises(ReflectionRejected, match="not in the verified scripture"):
        check('The text says "Yahweh will heal every broken heart and dry every tear."')


def test_altering_a_quoted_line_is_rejected():
    with pytest.raises(ReflectionRejected):
        check('"Yahweh is near to those who have a broken spirit and saves the lost"')


def test_short_quoted_phrases_are_ordinary_language():
    check('You are "not alone" and you can "be still" today.')


def test_responses_at_or_over_the_word_limit_are_rejected():
    just_under = " ".join(["word"] * 149)
    check(just_under)
    with pytest.raises(ReflectionRejected, match="150 words"):
        check(" ".join(["word"] * 150))


def test_word_limit_counts_both_fields():
    with pytest.raises(ReflectionRejected):
        check(" ".join(["word"] * 80), " ".join(["word"] * 80))

"""Keeps LLM output as commentary: it must never become altered or invented scripture (spec sections 1 and 6).

The hard guarantee is structural: the scripture sent to the client always comes from the database
and never from model output. These checks add a second layer on the commentary itself. They are
heuristics, not a theological review: they catch cited verse numbers and quoted passages that are
not in the verified text, and responses over the word limit.
"""

import re
from collections.abc import Iterable

# Quoted spans shorter than this are treated as ordinary phrases ("be still"), not quotations.
_MIN_QUOTED_WORDS = 4

_CHAPTER_VERSE = re.compile(r"\b\d{1,3}\s*:\s*\d{1,3}\b")
_QUOTED = re.compile(r'"([^"]+)"|“([^”]+)”')


class ReflectionRejected(ValueError):
    """The model output broke a spec constraint; the caller retries or falls back."""


def _squash(text: str) -> str:
    """Lowercase words only, so quote checks ignore punctuation, case and line breaks."""
    return " ".join(re.findall(r"\w+", text.lower()))


def _verse_numbers(text: str) -> set[str]:
    return {re.sub(r"\s+", "", match) for match in _CHAPTER_VERSE.findall(text)}


def check_reflection(texts: Iterable[str], *, source_book: str, scripture_text: str, max_words: int) -> None:
    """Raise ReflectionRejected unless the generated text is within limits and quotes nothing unverified."""
    joined = "\n".join(texts)

    word_count = len(joined.split())
    if word_count >= max_words:
        raise ReflectionRejected(f"{word_count} words; the limit is under {max_words}")

    unknown_refs = _verse_numbers(joined) - _verse_numbers(source_book)
    if unknown_refs:
        raise ReflectionRejected(f"cites verse numbers that are not the verified source: {sorted(unknown_refs)}")

    verified = _squash(scripture_text)
    for match in _QUOTED.finditer(joined):
        quoted = _squash(match.group(1) or match.group(2))
        if len(quoted.split()) >= _MIN_QUOTED_WORDS and quoted not in verified:
            raise ReflectionRejected("quotes text that is not in the verified scripture")

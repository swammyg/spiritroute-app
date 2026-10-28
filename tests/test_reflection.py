import asyncio
import json

import httpx
import pytest

from app.diagnostic import drivers_for
from app.schemas import Circle, Driver, Emotion
from app.services.llm_client import REFLECTION_JSON_SCHEMA, LLMUnavailable, OllamaClient
from app.services.output_guard import check_reflection
from app.services.reflection import (
    Reflection,
    ReflectionContext,
    ReflectionService,
    fallback_reflection,
    render_system_prompt,
)
from tests.fakes import FakeLLM, llm_reply

CTX = ReflectionContext(
    emotion=Emotion.SAD,
    circle=Circle.FAMILY,
    driver=Driver.BELONGING,
    belief_system="Faith-Alpha",
    source_book="Alpha Scroll 1:1",
    scripture_text="A sad family that finds belonging at last.",
)


def reflect(llm, *, max_attempts: int = 2, ctx: ReflectionContext = CTX) -> Reflection:
    service = ReflectionService(llm, max_attempts=max_attempts, max_words=150)
    return asyncio.run(service.reflect(ctx))


# --- prompt -------------------------------------------------------------------------------------


def test_system_prompt_fills_every_placeholder_and_keeps_the_json_example():
    prompt = render_system_prompt(CTX)
    for expected in (
        "- User Emotion: Sad",
        "- Relationship Context: Family",
        "- Root Core Issue: Belonging",
        "- User Belief System: Faith-Alpha",
        "Source: Alpha Scroll 1:1",
        "Text: A sad family that finds belonging at last.",
        "under 150 words total",
        '"word_of_hope":',
        '"prayer_reflection":',
    ):
        assert expected in prompt
    for placeholder in ("{user_emotion}", "{user_circle}", "{user_driver}", "{belief_system}"):
        assert placeholder not in prompt
    assert "{database_" not in prompt


def test_placeholder_lookalikes_inside_a_value_are_left_alone():
    ctx = ReflectionContext(**{**CTX.__dict__, "scripture_text": "Odd text with {user_driver} inside."})
    prompt = render_system_prompt(ctx)
    assert "Text: Odd text with {user_driver} inside." in prompt


# --- service ------------------------------------------------------------------------------------


def test_valid_reply_is_returned():
    llm = FakeLLM(llm_reply("Hope.", "Peace."))
    result = reflect(llm)
    assert (result.word_of_hope, result.prayer_reflection) == ("Hope.", "Peace.")
    assert len(llm.calls) == 1


def test_the_verified_scripture_and_context_are_what_the_llm_is_given():
    llm = FakeLLM(llm_reply())
    reflect(llm)
    system_prompt, user_prompt = llm.calls[0]
    assert "Text: A sad family that finds belonging at last." in system_prompt
    assert "JSON" in user_prompt


def test_prayer_returned_as_a_list_of_lines_is_joined():
    raw = json.dumps({"word_of_hope": "Hope.", "prayer_reflection": ["Line one.", "Line two."]})
    assert reflect(FakeLLM(raw)).prayer_reflection == "Line one.\nLine two."


def test_extra_keys_in_the_reply_are_ignored():
    raw = json.dumps({"word_of_hope": "Hope.", "prayer_reflection": "Peace.", "scripture_text": "INVENTED"})
    result = reflect(FakeLLM(raw))
    assert not hasattr(result, "scripture_text")


def test_malformed_reply_is_retried():
    llm = FakeLLM("this is not json", llm_reply("Second try.", "Peace."))
    assert reflect(llm).word_of_hope == "Second try."
    assert len(llm.calls) == 2


def test_reply_missing_a_field_is_retried():
    llm = FakeLLM(json.dumps({"word_of_hope": "Only half."}), llm_reply("Whole.", "Peace."))
    assert reflect(llm).word_of_hope == "Whole."


def test_reply_that_fails_the_scripture_guard_is_retried():
    invented = llm_reply('It says "love conquers every fear and heals every wound forever".', "Peace.")
    llm = FakeLLM(invented, llm_reply("Honest commentary.", "Peace."))
    assert reflect(llm).word_of_hope == "Honest commentary."
    assert len(llm.calls) == 2


def test_falls_back_when_every_attempt_is_rejected():
    llm = FakeLLM("{}")
    assert reflect(llm, max_attempts=3) == fallback_reflection(CTX)
    assert len(llm.calls) == 3


def test_falls_back_immediately_when_the_llm_is_unavailable():
    llm = FakeLLM(LLMUnavailable("connection refused"))
    assert reflect(llm, max_attempts=3) == fallback_reflection(CTX)
    assert len(llm.calls) == 1


def test_falls_back_when_there_is_no_llm():
    assert reflect(None) == fallback_reflection(CTX)


# --- fallback -----------------------------------------------------------------------------------


@pytest.mark.parametrize("emotion", list(Emotion))
@pytest.mark.parametrize("circle", list(Circle))
def test_fallback_passes_the_same_guard_for_every_wizard_combination(emotion, circle):
    for driver in drivers_for(emotion):
        ctx = ReflectionContext(emotion, circle, driver, "Faith-Alpha", "Psalms 34:18 (WEB)", "unused")
        result = fallback_reflection(ctx)
        check_reflection(
            (result.word_of_hope, result.prayer_reflection),
            source_book=ctx.source_book,
            scripture_text=ctx.scripture_text,
            max_words=150,
        )
        assert "Faith-Alpha" in result.prayer_reflection
        assert 3 <= len(result.prayer_reflection.splitlines()) <= 4


# --- Ollama client ------------------------------------------------------------------------------


def ollama_complete(handler) -> str:
    async def scenario() -> str:
        http = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://ollama.test")
        client = OllamaClient(
            base_url="http://ollama.test",
            model="llama3.2:3b",
            temperature=0.4,
            max_output_tokens=400,
            timeout=5,
            http=http,
        )
        try:
            return await client.complete("SYSTEM", "USER")
        finally:
            await client.aclose()

    return asyncio.run(scenario())


def test_ollama_client_sends_a_schema_constrained_chat_request():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"message": {"role": "assistant", "content": '{"ok": true}'}})

    assert ollama_complete(handler) == '{"ok": true}'
    assert seen["path"] == "/api/chat"
    body = seen["body"]
    assert body["model"] == "llama3.2:3b"
    assert body["stream"] is False
    assert body["format"] == REFLECTION_JSON_SCHEMA
    assert body["options"] == {"temperature": 0.4, "num_predict": 400}
    assert body["messages"] == [
        {"role": "system", "content": "SYSTEM"},
        {"role": "user", "content": "USER"},
    ]


@pytest.mark.parametrize(
    "handler",
    [
        lambda request: httpx.Response(500, text="boom"),
        lambda request: httpx.Response(200, text="<html>not json</html>"),
        lambda request: httpx.Response(200, json={"unexpected": "shape"}),
        lambda request: httpx.Response(200, json=["not", "an", "object"]),
        lambda request: (_ for _ in ()).throw(httpx.ConnectError("connection refused")),
    ],
    ids=["http-500", "not-json", "missing-message", "wrong-type", "connection-refused"],
)
def test_ollama_client_reports_any_failure_as_llm_unavailable(handler):
    with pytest.raises(LLMUnavailable):
        ollama_complete(handler)

"""Client for a small local LLM served by Ollama (spec sections 1 and 6)."""

from typing import Protocol

import httpx

# Constrains Ollama's decoding to exactly the spec's output format (section 6).
REFLECTION_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "word_of_hope": {"type": "string"},
        "prayer_reflection": {"type": "string"},
    },
    "required": ["word_of_hope", "prayer_reflection"],
}


class LLMUnavailable(RuntimeError):
    """The model server could not be reached, or answered with something unusable."""


class LLMClient(Protocol):
    async def complete(self, system_prompt: str, user_prompt: str) -> str: ...

    async def aclose(self) -> None: ...


class OllamaClient:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        temperature: float,
        max_output_tokens: int,
        timeout: float,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self._model = model
        self._options = {"temperature": temperature, "num_predict": max_output_tokens}
        self._http = http or httpx.AsyncClient(base_url=base_url, timeout=timeout)

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        body = {
            "model": self._model,
            "stream": False,
            "format": REFLECTION_JSON_SCHEMA,
            "keep_alive": "30m",
            "options": self._options,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        try:
            response = await self._http.post("/api/chat", json=body)
            response.raise_for_status()
            return response.json()["message"]["content"]
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise LLMUnavailable(f"{type(exc).__name__}: {exc}") from exc

    async def aclose(self) -> None:
        await self._http.aclose()

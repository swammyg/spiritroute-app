"""Service container: built once at startup and shared by every request."""

from dataclasses import dataclass

from fastapi import Request

from app.config import Settings
from app.services.embedding import SentenceTransformerEmbedder
from app.services.llm_client import OllamaClient
from app.services.query_vectors import QueryVectors
from app.services.reflection import ReflectionService
from app.services.vector_store import ScriptureStore


@dataclass
class Services:
    queries: QueryVectors
    store: ScriptureStore
    reflections: ReflectionService

    async def aclose(self) -> None:
        await self.reflections.aclose()
        self.store.close()


def build_services(settings: Settings) -> Services:
    # The embedding model is only needed to embed the 64 query sentences, so it is not kept afterwards.
    queries = QueryVectors(
        SentenceTransformerEmbedder(settings.embedding_model, settings.embedding_dim),
        center_queries=settings.query_centering,
    )
    store = ScriptureStore.from_settings(settings)
    store.ensure_collection()
    llm = (
        OllamaClient(
            base_url=settings.ollama_base_url,
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_output_tokens=settings.llm_max_output_tokens,
            timeout=settings.llm_timeout_seconds,
        )
        if settings.llm_enabled
        else None
    )
    reflections = ReflectionService(llm, max_attempts=settings.llm_max_attempts, max_words=settings.llm_max_words)
    return Services(queries=queries, store=store, reflections=reflections)


def get_services(request: Request) -> Services:
    return request.app.state.services


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings

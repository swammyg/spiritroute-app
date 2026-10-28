import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.dependencies import Services
from app.main import create_app
from app.services.query_vectors import QueryVectors
from app.services.reflection import ReflectionService
from tests.fakes import FakeEmbedder, make_store


@pytest.fixture
def embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture
def make_client(embedder):
    """Build a TestClient over fake services. `llm=None` means no LLM, so the fallback template is used."""
    clients: list[TestClient] = []

    def _make(
        llm=None,
        *,
        store=None,
        queries=None,
        settings: Settings | None = None,
        max_attempts: int = 2,
    ) -> TestClient:
        services = Services(
            queries=queries or QueryVectors(embedder, center_queries=True),
            store=store or make_store(embedder),
            reflections=ReflectionService(llm, max_attempts=max_attempts, max_words=150),
        )
        app = create_app(settings or Settings(_env_file=None, llm_enabled=llm is not None), services)
        client = TestClient(app)
        client.__enter__()
        clients.append(client)
        return client

    yield _make
    for client in clients:
        client.__exit__(None, None, None)

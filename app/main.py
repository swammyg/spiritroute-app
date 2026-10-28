"""FastAPI application factory. Run with: uvicorn app.main:app"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.dependencies import Services, build_services
from app.routes import health_router, router

logger = logging.getLogger("spiritroute")


def create_app(settings: Settings | None = None, services: Services | None = None) -> FastAPI:
    """Pass `services` to run against prebuilt (e.g. fake) services instead of loading the models."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        app.state.services = services or build_services(settings)
        if app.state.services.store.count() == 0:
            logger.warning("The scripture collection is empty. Load it with: python -m app.ingest <file.jsonl>")
        yield
        if services is None:
            await app.state.services.aclose()

    app = FastAPI(
        title="SpiritRoute AI",
        version="1.0.0",
        description="Three diagnostic answers in, one verified scripture plus a short Word of Hope and prayer out.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def no_store(request: Request, call_next) -> Response:
        # Privacy first (spec section 1): nothing personal should be cached by a browser or proxy.
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    app.include_router(router, prefix="/api/v1")
    app.include_router(health_router)
    return app


app = create_app()

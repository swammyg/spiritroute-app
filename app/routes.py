"""HTTP routes."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool

from app.config import Settings
from app.dependencies import Services, get_app_settings, get_services
from app.diagnostic import driver_error, drivers_for
from app.schemas import (
    BeliefSystems,
    Circle,
    CrisisResponse,
    DiagnosticOptions,
    Emotion,
    Health,
    ResolveHeartRequest,
    ScriptureResponse,
)
from app.services.reflection import ReflectionContext
from app.services.safety import crisis_response, needs_crisis_override

logger = logging.getLogger(__name__)

router = APIRouter()
health_router = APIRouter()

ServicesDep = Annotated[Services, Depends(get_services)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]


@router.get("/diagnostic-options", response_model=DiagnosticOptions, summary="Options for the 3-step wizard")
def diagnostic_options() -> DiagnosticOptions:
    """Step 3 options depend on the Step 1 answer, so they are returned per emotion."""
    return DiagnosticOptions(
        emotions=list(Emotion),
        circles=list(Circle),
        drivers_by_emotion={emotion: list(drivers_for(emotion)) for emotion in Emotion},
    )


@router.get("/belief-systems", response_model=BeliefSystems, summary="Belief systems that have scriptures loaded")
async def belief_systems(services: ServicesDep) -> BeliefSystems:
    return BeliefSystems(belief_systems=await run_in_threadpool(services.store.list_belief_systems))


@router.post(
    "/resolve-heart",
    response_model=ScriptureResponse | CrisisResponse,
    summary="Turn the three wizard answers into a verified scripture, a Word of Hope and a prayer",
    responses={
        404: {"description": "No scripture is loaded for this belief system"},
        422: {"description": "Invalid answers, or a Step 3 driver that does not fit the Step 1 emotion"},
        500: {"description": "Database lookup failure"},
    },
)
async def resolve_heart(
    payload: ResolveHeartRequest,
    services: ServicesDep,
    settings: SettingsDep,
) -> ScriptureResponse | CrisisResponse:
    # Safety comes first (spec section 7): on a crisis signal nothing below runs, so the database,
    # the embedding model and the LLM are never touched.
    if needs_crisis_override(payload, settings.crisis_selection_triggers):
        logger.info("Crisis override returned")
        return crisis_response()

    if problem := driver_error(payload.user_emotion, payload.user_driver):
        raise HTTPException(status_code=422, detail=problem)

    vector = services.queries.for_answer(payload.user_emotion, payload.user_circle, payload.user_driver)

    # The belief-system filter is applied inside the vector search, never after it.
    try:
        match = await run_in_threadpool(services.store.search, vector, payload.belief_system)
    except Exception:
        logger.exception("Scripture lookup failed")
        raise HTTPException(status_code=500, detail="Database lookup failure") from None
    if match is None:
        raise HTTPException(status_code=404, detail="No matching scripture found")

    reflection = await services.reflections.reflect(
        ReflectionContext(
            emotion=payload.user_emotion,
            circle=payload.user_circle,
            driver=payload.user_driver,
            belief_system=match.belief_system,
            source_book=match.source_book,
            scripture_text=match.content,
        )
    )
    # scripture_text is the database row, verbatim. Only the two reflection fields come from the LLM.
    return ScriptureResponse(
        source=match.source_book,
        scripture_text=match.content,
        word_of_hope=reflection.word_of_hope,
        prayer_reflection=reflection.prayer_reflection,
    )


@health_router.get("/health", response_model=Health, summary="Liveness check")
async def health(services: ServicesDep, settings: SettingsDep) -> Health:
    return Health(
        status="ok",
        scriptures=await run_in_threadpool(services.store.count),
        llm_enabled=settings.llm_enabled,
    )

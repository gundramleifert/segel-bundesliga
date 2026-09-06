"""Admin endpoints: compute, validate, publish pairing lists (Story VA-3)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.db import get_session
from app.i18n import Locale, resolve_locale, tr
from app.jobs import Job, JobStatus, jobs
from app.models import Event
from app.models.racing import BOAT_COLORS
from app.pairing import BoatSpec, load_pairing_yaml
from app.pairing.catalog import KatalogFehler, katalog, lade, mische
from app.pairing.generator import (
    GenerationRequest,
    OptimizerSettings,
    PairingGeneratorError,
    generate_pairing,
)
from app.pairing.importer import PairingImportError
from app.schemas.admin import (
    JobOut,
    PairingImportRequest,
    PairingJobRequest,
    PublishRequest,
    PublishResult,
)
from app.services.pairing_service import (
    PairingDraft,
    PairingPublishError,
    publish_pairing,
    teams_for_event,
)

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])

# Reduced settings for a quick preview. The default corresponds to the
# configuration of actual matchdays and takes correspondingly long.
FAST = OptimizerSettings(
    loops=400, match_individuals=60, boat_individuals=100, swap_teams=30,
    swap_boats=40, swap_races=20,
)


@router.post(
    "/events/{event_id}/pairing/jobs",
    response_model=JobOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Compute pairing list",
)
async def start_pairing_job(
    event_id: int,
    request: PairingJobRequest,
    session: AsyncSession = Depends(get_session),
    locale: Locale = Depends(resolve_locale),
) -> JobOut:
    """Starts the computation in the background.

    Depending on settings, the run takes seconds to many minutes — that's why it's a job with
    progress rather than a waiting request. The result is **not** automatically
    published; the organizer sees the quality report first.
    """
    event = await _event_by_id(session, event_id, locale)
    teams = await teams_for_event(session, event)
    if len(teams) < request.boats:
        raise HTTPException(
            status_code=422,
            detail=tr(
                locale,
                en=f"Only {len(teams)} teams registered, but {request.boats} boats.",
                de=f"Nur {len(teams)} Teams gemeldet, aber {request.boats} Boote.",
            ),
        )
    if len(teams) % request.boats:
        raise HTTPException(
            status_code=422,
            detail=tr(
                locale,
                en=(
                    f"{len(teams)} teams cannot be evenly distributed across {request.boats} "
                    "boats. The tool pads with empty slots — we're not prepared for that yet."
                ),
                de=(
                    f"{len(teams)} Teams lassen sich nicht gleichmäßig auf {request.boats} "
                    "Boote verteilen. Das Werkzeug füllt dann mit Leerplätzen auf — dafür ist "
                    "die Liste bei uns noch nicht vorgesehen."
                ),
            ),
        )

    team_ids = [team.id for team in teams]
    generation = GenerationRequest(
        teams=[team.name for team in teams],
        boats=[
            BoatSpec(number=n + 1, color=BOAT_COLORS[n % len(BOAT_COLORS)])
            for n in range(request.boats)
        ],
        flights=request.flights,
        title=event.title,
        optimizer=(
            FAST if request.effort == "fast" else OptimizerSettings(seed=request.seed)
        ),
    )

    async def work(job: Job) -> PairingDraft:
        result = await generate_pairing(
            generation,
            on_progress=lambda p: job.report(p.fraction, p.message),
        )
        draft = PairingDraft.from_import(result.pairing, team_ids)
        draft.quality = result.summary()
        return draft

    return _job_out(jobs.start("pairing", work))


@router.get("/jobs/{job_id}", response_model=JobOut, summary="Job status")
async def get_job(job_id: str, locale: Locale = Depends(resolve_locale)) -> JobOut:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail=tr(
                locale,
                en="This job does not exist (anymore).",
                de="Diesen Auftrag gibt es nicht (mehr).",
            ),
        )
    return _job_out(job)


@router.delete("/jobs/{job_id}", response_model=JobOut, summary="Cancel job")
async def cancel_job(job_id: str, locale: Locale = Depends(resolve_locale)) -> JobOut:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail=tr(
                locale,
                en="This job does not exist (anymore).",
                de="Diesen Auftrag gibt es nicht (mehr).",
            ),
        )
    jobs.cancel(job_id)
    return _job_out(job)


@router.post(
    "/events/{event_id}/pairing/publish",
    response_model=PublishResult,
    summary="Publish computed list",
)
async def publish_job_result(
    event_id: int,
    request: PublishRequest,
    session: AsyncSession = Depends(get_session),
    locale: Locale = Depends(resolve_locale),
) -> PublishResult:
    event = await _event_by_id(session, event_id, locale)
    job = jobs.get(request.job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail=tr(
                locale,
                en="This job does not exist (anymore).",
                de="Diesen Auftrag gibt es nicht (mehr).",
            ),
        )
    if job.status != JobStatus.DONE:
        raise HTTPException(
            status_code=409,
            detail=tr(
                locale,
                en=f"The job is not complete (status: {job.status}).",
                de=f"Der Auftrag ist nicht abgeschlossen (Stand: {job.status}).",
            ),
        )
    draft = job.result
    if not isinstance(draft, PairingDraft):
        raise HTTPException(
            status_code=409,
            detail=tr(
                locale,
                en="This job contains no pairing list.",
                de="Dieser Auftrag enthält keine Pairing-Liste.",
            ),
        )

    return PublishResult(**await _publish(session, event, draft), quality=draft.quality)


class KatalogEintragOut(BaseModel):
    """A finished size from the catalog."""

    name: str
    teams: int
    boats: int
    flights: int
    races: int


class AusKatalog(BaseModel):
    seed: int = Field(
        default=0,
        description=(
            "Seed value for shuffling starting positions. The same value always produces the same "
            "draw — it can be used to reconstruct it in case of dispute."
        ),
    )


@router.get(
    "/pairing/catalog",
    response_model=list[KatalogEintragOut],
    summary="Finished pairing lists",
)
async def pairing_katalog() -> list[KatalogEintragOut]:
    """Which sizes are available without computing.

    A size is completely determined by teams, boats, and flights — which club
    sits at which starting position is decided only when shuffling.
    """
    return [
        KatalogEintragOut(
            name=eintrag.name,
            teams=eintrag.teams,
            boats=eintrag.boats,
            flights=eintrag.flights,
            races=eintrag.races,
        )
        for eintrag in katalog()
    ]


@router.post(
    "/events/{event_id}/pairing/from-catalog",
    response_model=PublishResult,
    summary="Take finished list from catalog",
)
async def pairing_aus_katalog(
    event_id: int,
    request: AusKatalog | None = None,
    session: AsyncSession = Depends(get_session),
) -> PublishResult:
    """Takes the stored list for this size and shuffles the starting positions.

    The standard case, and it takes **milliseconds**: the expensive optimization has run
    once and is stored in the catalog. Only shuffled is who sits at which starting position —
    boat distribution, matchups, and boat changes are unaffected because they depend on
    the structure of the list, not the names.

    If no entry matches the size, the path remains through the compute job.
    """
    event = await _event_by_id(session, event_id)
    teams = await teams_for_event(session, event)

    try:
        pairing = lade(len(teams), event.boat_count, event.flight_count)
    except KatalogFehler as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    seed = request.seed if request else 0
    draft = PairingDraft.from_import(mische(pairing, seed), [team.id for team in teams])
    return PublishResult(**await _publish(session, event, draft), quality=draft.quality)


@router.post(
    "/events/{event_id}/pairing/import",
    response_model=PublishResult,
    summary="Import finished list",
)
async def import_pairing(
    event_id: int,
    request: PairingImportRequest,
    session: AsyncSession = Depends(get_session),
    locale: Locale = Depends(resolve_locale),
) -> PublishResult:
    """Imports a draw created elsewhere — the standard until now.

    Team index assignment follows the order in ``schedule_cfg.yml``: index 0 is
    the first team named there. Names are only for verification, not compared.
    """
    event = await _event_by_id(session, event_id, locale)
    teams = await teams_for_event(session, event)

    try:
        pairing = load_pairing_yaml(request.schedule_config, request.pairing_list)
    except PairingImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if len(pairing.teams) != len(teams):
        raise HTTPException(
            status_code=422,
            detail=tr(
                locale,
                en=(
                    f"The list names {len(pairing.teams)} teams, {len(teams)} are registered. "
                    "First reconcile the registrations, then import the draw."
                ),
                de=(
                    f"Die Liste nennt {len(pairing.teams)} Teams, gemeldet sind {len(teams)}. "
                    "Erst die Meldungen abgleichen, dann die Auslosung übernehmen."
                ),
            ),
        )

    draft = PairingDraft.from_import(pairing, [team.id for team in teams])
    return PublishResult(**await _publish(session, event, draft), quality=draft.quality)


async def _publish(session: AsyncSession, event: Event, draft: PairingDraft) -> dict[str, int]:
    try:
        return await publish_pairing(session, event, draft)
    except PairingPublishError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PairingGeneratorError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


async def _event_by_id(session: AsyncSession, event_id: int, locale: Locale | None = None) -> Event:
    event = (
        await session.execute(select(Event).where(Event.id == event_id))
    ).scalar_one_or_none()
    if event is None:
        if locale is not None:
            detail = tr(
                locale,
                en=f"Matchday {event_id} not found",
                de=f"Spieltag {event_id} nicht gefunden",
            )
        else:
            detail = f"Matchday {event_id} not found"
        raise HTTPException(status_code=404, detail=detail)
    return event


def _job_out(job: Job) -> JobOut:
    quality = job.result.quality if isinstance(job.result, PairingDraft) else {}
    return JobOut(
        id=job.id,
        kind=job.kind,
        status=job.status,
        progress=job.progress,
        message=job.message,
        error=job.error,
        created_at=job.created_at,
        finished_at=job.finished_at,
        quality=quality,
    )

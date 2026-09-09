"""Admin endpoints: compute, validate, publish pairing lists (Story VA-3);
enter and correct race results (Story WL-2).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import require_admin, require_race_officer
from app.db import get_session
from app.i18n import Locale, resolve_locale, tr
from app.jobs import Job, JobStatus, jobs
from app.models import AuditLog, Event
from app.models.auth import User
from app.models.org import Team, TeamStatus
from app.models.racing import BOAT_COLORS, Boat, Flight, Race, RaceEntry, RaceStatus, ResultCode
from app.pairing import BoatSpec, load_pairing_yaml
from app.pairing.catalog import CatalogError, catalog_entries, load_entry, shuffle_pairing
from app.pairing.generator import (
    GenerationRequest,
    OptimizerSettings,
    PairingGeneratorError,
    generate_pairing,
)
from app.pairing.importer import PairingImportError
from app.problems import Problem
from app.schemas.admin import (
    AdminRaceOut,
    AdminRacesOut,
    JobOut,
    PairingImportRequest,
    PairingJobRequest,
    PublishRequest,
    PublishResult,
    RaceEntryOut,
    RaceResultsIn,
    RaceResultsOut,
)
from app.schemas.public import BoatOut, ClubOut, TeamOut
from app.services import (
    CATALOG_REASON,
    recompute_event,
    recompute_series,
    require_editable_configuration,
    require_ready,
)
from app.services.pairing_service import (
    PairingDraft,
    PairingPublishError,
    publish_pairing,
    teams_for_event,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])

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
    dependencies=[Depends(require_admin)],
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

    The event has to be ready (Story VA-8) — except for the catalog reason, since computing
    a list is exactly what one does when the catalog holds none — and its configuration
    must not be frozen: once a race has started, the list underneath it stays.
    """
    event = await _event_by_id(session, event_id, locale)
    await require_editable_configuration(session, event.id)
    await require_ready(session, event, ignore={CATALOG_REASON})
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


@router.get(
    "/jobs/{job_id}",
    response_model=JobOut,
    dependencies=[Depends(require_admin)],
    summary="Job status",
)
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


@router.delete(
    "/jobs/{job_id}",
    response_model=JobOut,
    dependencies=[Depends(require_admin)],
    summary="Cancel job",
)
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
    dependencies=[Depends(require_admin)],
    summary="Publish computed list",
)
async def publish_job_result(
    event_id: int,
    request: PublishRequest,
    session: AsyncSession = Depends(get_session),
    locale: Locale = Depends(resolve_locale),
) -> PublishResult:
    event = await _event_by_id(session, event_id, locale)
    await require_editable_configuration(session, event.id)
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


class CatalogEntryOut(BaseModel):
    """A finished size from the catalog."""

    name: str
    teams: int
    boats: int
    flights: int
    races: int


class FromCatalogRequest(BaseModel):
    seed: int = Field(
        default=0,
        description=(
            "Seed value for shuffling starting positions. The same value always produces the same "
            "draw — it can be used to reconstruct it in case of dispute."
        ),
    )


@router.get(
    "/pairing/catalog",
    response_model=list[CatalogEntryOut],
    dependencies=[Depends(require_admin)],
    summary="Finished pairing lists",
)
async def list_pairing_catalog() -> list[CatalogEntryOut]:
    """Which sizes are available without computing.

    A size is completely determined by teams, boats, and flights — which club
    sits at which starting position is decided only when shuffling.
    """
    return [
        CatalogEntryOut(
            name=entry.name,
            teams=entry.teams,
            boats=entry.boats,
            flights=entry.flights,
            races=entry.races,
        )
        for entry in catalog_entries()
    ]


@router.post(
    "/events/{event_id}/pairing/from-catalog",
    response_model=PublishResult,
    dependencies=[Depends(require_admin)],
    summary="Take finished list from catalog",
)
async def pairing_from_catalog(
    event_id: int,
    request: FromCatalogRequest | None = None,
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
    # Nothing is drawn against a running matchday, and nothing is drawn for an incomplete
    # setup (Story VA-8). The readiness check answers both of the questions this endpoint
    # used to ask itself — too few teams registered, and no catalog entry for these
    # dimensions — with the same codes and statuses it always raised, so a single-cause
    # failure reads exactly as before. See `app/services/event_readiness.py`.
    await require_editable_configuration(session, event.id)
    await require_ready(session, event)

    teams = await teams_for_event(session, event)
    try:
        pairing = load_entry(len(teams), event.boat_count, event.flight_count)
    except CatalogError as exc:  # pragma: no cover - readiness already ruled this out
        raise Problem(
            404,
            CATALOG_REASON,
            "No pre-computed pairing list is stored for this size.",
            teams=len(teams),
            boats=event.boat_count,
            flights=event.flight_count,
            available=[f"{e.teams}/{e.boats}/{e.flights}" for e in catalog_entries()],
        ) from exc

    seed = request.seed if request else 0
    draft = PairingDraft.from_import(shuffle_pairing(pairing, seed), [team.id for team in teams])
    return PublishResult(**await _publish(session, event, draft), quality=draft.quality)


@router.post(
    "/events/{event_id}/pairing/import",
    response_model=PublishResult,
    dependencies=[Depends(require_admin)],
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

    An imported draw brings its own dimensions, so the catalog reason doesn't apply — but
    the rest of the setup must add up, and a started matchday keeps the list it is sailing
    (Story VA-8).
    """
    event = await _event_by_id(session, event_id, locale)
    await require_editable_configuration(session, event.id)
    await require_ready(session, event, ignore={CATALOG_REASON})
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


# ------------------------------------------------------------ Race results (Story WL-2)

# Codes for which the underlying finish order (``finish_position``) is real and thus
# participates in the "no two boats in the same place" check — RDG and the
# not-a-finish codes (DNS, DNF, ...) carry no position at all.
_POSITION_CODES = (ResultCode.FINISHED, ResultCode.ZFP, ResultCode.SCP)


@router.get(
    "/events/{event_id}/races",
    response_model=AdminRacesOut,
    dependencies=[Depends(require_race_officer)],
    summary="Pairing and current results, for the entry screen",
)
async def get_admin_races(
    event_id: int,
    session: AsyncSession = Depends(get_session),
    locale: Locale = Depends(resolve_locale),
) -> AdminRacesOut:
    """Everything the race committee needs to enter or correct results.

    Unlike the public pairing list (``app.routers.public.get_pairing``), this includes
    unfinished races and the current result state of every entry — the raw fields plus the
    derived ``points``/``is_discarded`` so a correction's effect is visible immediately.
    """
    event = await _event_by_id(session, event_id, locale)

    boats = list(
        (
            await session.execute(
                select(Boat).where(Boat.event_id == event.id).order_by(Boat.number)
            )
        ).scalars()
    )

    teams = await _teams_of_event(session, event.id)

    stmt = (
        select(Race, RaceEntry, Flight, Boat.number)
        .join(Flight, Race.flight_id == Flight.id)
        .join(RaceEntry, RaceEntry.race_id == Race.id)
        .join(Boat, RaceEntry.boat_id == Boat.id)
        .where(Flight.event_id == event.id)
        .order_by(Race.sequence, Boat.number)
    )
    races: dict[int, AdminRaceOut] = {}
    for race, entry, flight, boat_number in (await session.execute(stmt)).all():
        row = races.get(race.id)
        if row is None:
            row = AdminRaceOut(
                id=race.id,
                sequence=race.sequence,
                flight=flight.number,
                race_in_flight=race.number_in_flight,
                status=race.status,
                version=race.version,
                entries=[],
            )
            races[race.id] = row
        team = teams.get(entry.team_id)
        if team is None:
            continue
        row.entries.append(
            RaceEntryOut(
                boat_number=boat_number,
                team=team,
                code=entry.code,
                finish_position=entry.finish_position,
                redress_points=entry.redress_points,
                points=entry.points,
                is_discarded=entry.is_discarded,
            )
        )

    return AdminRacesOut(
        event_id=event.id,
        boats=[BoatOut.model_validate(boat) for boat in boats],
        races=[races[key] for key in sorted(races, key=lambda race_id: races[race_id].sequence)],
    )


@router.put(
    "/events/{event_id}/races/{race_id}/result",
    response_model=RaceResultsOut,
    summary="Enter or correct a race's result",
)
async def put_race_result(
    event_id: int,
    race_id: int,
    request: RaceResultsIn,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(require_race_officer),
) -> RaceResultsOut:
    """Writes the raw result for every submitted boat in one race.

    ``code``/``finish_position``/``redress_points`` are the authoritative raw data
    (``docs/concepts.md``, "Points are derived, not entered"): after writing, the event's
    (and, if it belongs to one, the series') standings are recomputed immediately so
    ``points``/``is_discarded`` and the published tables never lag behind a correction.

    A boat not mentioned in ``results`` keeps its current result — this also allows
    fixing a single entry after a protest without resubmitting the whole race.
    """
    event = await _event_by_id(session, event_id)

    race = (
        await session.execute(
            select(Race)
            .join(Flight, Race.flight_id == Flight.id)
            .where(Race.id == race_id, Flight.event_id == event.id)
        )
    ).scalar_one_or_none()
    if race is None:
        raise Problem(
            404,
            "race-not-found",
            f"Race {race_id} does not belong to event {event_id}.",
        )

    entry_rows = (
        await session.execute(
            select(RaceEntry, Boat.number)
            .join(Boat, RaceEntry.boat_id == Boat.id)
            .where(RaceEntry.race_id == race.id)
        )
    ).all()
    entry_by_boat: dict[int, RaceEntry] = {number: entry for entry, number in entry_rows}

    updates: dict[int, tuple[ResultCode, int | None, float | None]] = {}
    for result in request.results:
        entry = entry_by_boat.get(result.boat_number)
        if entry is None:
            raise Problem(
                422,
                "race-result-unknown-boat",
                f"Boat {result.boat_number} has no entry in race {race_id}.",
                boat_number=result.boat_number,
            )
        try:
            code = ResultCode(result.code)
        except ValueError as exc:
            raise Problem(
                422,
                "race-result-invalid-code",
                f"'{result.code}' is not a valid result code.",
                boat_number=result.boat_number,
            ) from exc

        if code in _POSITION_CODES and result.finish_position is None:
            raise Problem(
                422,
                "race-result-position-required",
                f"Boat {result.boat_number}: a finish position is required for {code}.",
                boat_number=result.boat_number,
            )
        if code == ResultCode.RDG and result.redress_points is None:
            raise Problem(
                422,
                "race-result-redress-required",
                f"Boat {result.boat_number}: redress points are required for RDG.",
                boat_number=result.boat_number,
            )

        updates[result.boat_number] = (
            code,
            result.finish_position if code in _POSITION_CODES else None,
            result.redress_points if code == ResultCode.RDG else None,
        )

    # No two boats may claim the same finish position — across the *resulting* state of
    # the race, including entries this request doesn't touch.
    position_owners: dict[int, int] = {}
    for boat_number, entry in entry_by_boat.items():
        if boat_number in updates:
            code, position, _ = updates[boat_number]
        else:
            code = ResultCode(entry.code) if entry.code is not None else None
            position = entry.finish_position
        if code not in _POSITION_CODES or position is None:
            continue
        if position in position_owners:
            raise Problem(
                422,
                "race-result-duplicate-position",
                f"Finish position {position} is claimed by more than one boat.",
                finish_position=position,
            )
        position_owners[position] = boat_number

    original_version = race.version
    overwrote_existing = request.version is not None and request.version != original_version
    if overwrote_existing:
        # Someone else changed this race since the submitter last loaded it — the later
        # entry still wins (this is a rocking-boat matchday, not a place for a hard
        # conflict error), but per WL-2 ("the overridden status is not lost but logged")
        # the state about to be discarded is recorded first, not silently dropped.
        session.add(
            AuditLog(
                entity_type="race",
                entity_id=race.id,
                action="result_overwrite",
                actor=acting.email,
                payload={
                    "submitted_on_version": request.version,
                    "actual_version": original_version,
                    "discarded_entries": {
                        str(boat_number): {
                            "code": entry_by_boat[boat_number].code,
                            "finish_position": entry_by_boat[boat_number].finish_position,
                            "redress_points": entry_by_boat[boat_number].redress_points,
                        }
                        for boat_number in updates
                    },
                },
            )
        )

    for boat_number, (code, position, redress_points) in updates.items():
        entry = entry_by_boat[boat_number]
        entry.code = code
        entry.finish_position = position
        entry.redress_points = redress_points

    race.version += 1
    if all(entry.code is not None for entry in entry_by_boat.values()):
        race.status = RaceStatus.FINISHED

    await recompute_event(session, event.id)
    if event.series_id is not None:
        await recompute_series(session, event.series_id)

    await session.commit()

    return RaceResultsOut(
        race_id=race.id,
        sequence=race.sequence,
        status=race.status,
        version=race.version,
        applied=True,
        overwrote_existing=overwrote_existing,
    )


async def _teams_of_event(session: AsyncSession, event_id: int) -> dict[int, TeamOut]:
    """The teams participating in this event, keyed by team id.

    Local to the admin router — the equivalent in ``app.routers.public`` is a private
    helper of that module.
    """
    result = await session.execute(
        select(Team)
        .options(selectinload(Team.club))
        .where(Team.event_id == event_id, Team.status == TeamStatus.ACCEPTED)
    )
    return {
        team.id: TeamOut(id=team.id, name=team.name, club=ClubOut.model_validate(team.club))
        for team in result.scalars()
    }


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

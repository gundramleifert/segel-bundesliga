"""Tracking against the database: the course as laid, the trackers, the fixes, the picture.

Everything computed here is derived from stored facts on every call and never written back
(decision 12): the analysis in ``app.tracking.analysis`` gets the fixes since the start and
answers with legs, distances and ranks. This module only knows *where* those facts are.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.live import event_topic, hub
from app.models import (
    Boat,
    Course,
    Event,
    Fix,
    Flight,
    Mark,
    Race,
    RaceEntry,
    RaceStatus,
    Team,
    Tracker,
    Venue,
)
from app.schemas.public import ClubOut, TeamOut
from app.schemas.tracking import (
    CourseIn,
    CourseOut,
    DefaultCourseIn,
    FixIn,
    LaylineOut,
    LiveBoatOut,
    LiveRaceInfo,
    LiveRaceOut,
    MarkOut,
    TrackerOut,
)
from app.tracking.analysis import default_pipeline
from app.tracking.course import Course as CourseGeometry
from app.tracking.course import MarkRole, lay_course
from app.tracking.geo import XY, LocalTangentPlane, bearing_deg
from app.tracking.geo import Fix as GeoFix
from app.tracking.polar import KNOT
from app.tracking.ranking import metres_to_go
from app.tracking.settings import tracking_settings
from app.tracking.tactics import laylines, leader_line


def _aware(value: datetime) -> datetime:
    """SQLite hands timezone-aware columns back naive; they were written in UTC."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


# ------------------------------------------------------------------------- course


async def active_course(session: AsyncSession, event_id: int) -> Course | None:
    """The newest course laid for the event — a re-lay is a new row (see the model)."""
    return (
        await session.execute(
            select(Course)
            .options(selectinload(Course.marks))
            .where(Course.event_id == event_id)
            .order_by(Course.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


def course_origin(course: Course) -> tuple[float, float]:
    lats = [m.lat for m in course.marks]
    lons = [m.lon for m in course.marks]
    return sum(lats) / len(lats), sum(lons) / len(lons)


def course_geometry(course: Course) -> tuple[CourseGeometry, LocalTangentPlane]:
    """The stored marks, projected around their centre."""
    projection = LocalTangentPlane(*course_origin(course))
    marks = {MarkRole(m.role): projection.to_xy(m.lat, m.lon) for m in course.marks}
    return (
        CourseGeometry(
            marks,
            laps=course.laps,
            finish_upwind=course.finish_upwind,
            finish_pin_side=course.finish_pin_side,  # type: ignore[arg-type]
        ),
        projection,
    )


def course_out(course: Course) -> CourseOut:
    geometry, _ = course_geometry(course)
    return CourseOut(
        id=course.id,
        event_id=course.event_id,
        laps=course.laps,
        finish_upwind=course.finish_upwind,
        finish_pin_side=course.finish_pin_side,
        tws_kn=course.tws_kn,
        wind_from_deg=course.wind_from_deg,
        marks=[MarkOut(role=m.role, lat=m.lat, lon=m.lon) for m in course.marks],
        waypoints=[w.name for w in geometry.waypoints()],
        created_at=_aware(course.created_at),
    )


async def store_course(session: AsyncSession, event: Event, request: CourseIn) -> Course:
    """A new course row from the committee's marks. The caller commits."""
    now = datetime.now(UTC)
    course = Course(
        event_id=event.id,
        laps=request.laps,
        finish_upwind=request.finish_upwind,
        finish_pin_side=request.finish_pin_side,
        tws_kn=request.tws_kn,
        wind_from_deg=request.wind_from_deg,
    )
    course.marks = [Mark(role=m.role, lat=m.lat, lon=m.lon, set_at=now) for m in request.marks]
    session.add(course)
    await session.flush()
    return course


async def lay_default_course(
    session: AsyncSession, event: Event, request: DefaultCourseIn
) -> Course:
    """The textbook course around the venue (or the given point). The caller commits."""
    lat, lon = request.lat, request.lon
    if lat is None or lon is None:
        venue = await session.get(Venue, event.venue_id) if event.venue_id else None
        if venue is not None and venue.lat is not None and venue.lon is not None:
            lat, lon = float(venue.lat), float(venue.lon)
        else:
            lat, lon = tracking_settings.default_lat, tracking_settings.default_lon
    wind = (
        tracking_settings.default_wind_from_deg
        if request.wind_from_deg is None
        else request.wind_from_deg
    )
    geometry = lay_course(
        XY(0.0, 0.0),
        wind_from_deg=wind,
        leg_length=request.leg_length_m,
        laps=request.laps,
        finish_upwind=request.finish_upwind,
        finish_pin_side=request.finish_pin_side,
    )
    projection = LocalTangentPlane(lat, lon)
    marks = []
    for role, xy in geometry.marks.items():
        mark_lat, mark_lon = projection.to_geo(xy)
        marks.append({"role": str(role), "lat": mark_lat, "lon": mark_lon})
    return await store_course(
        session,
        event,
        CourseIn(
            marks=marks,  # type: ignore[arg-type]
            laps=request.laps,
            finish_upwind=request.finish_upwind,
            finish_pin_side=request.finish_pin_side,
            wind_from_deg=wind,
        ),
    )


# ----------------------------------------------------------------------- trackers


async def ensure_trackers(session: AsyncSession, event: Event) -> list[Tracker]:
    """One tracker per boat of the event plus the committee boat, created on first use.

    Tokens are random and issued here, never typed on the water; the race-control screen
    shows them as QR codes (Story L-4). The caller commits.
    """
    boats = list(
        (
            await session.execute(
                select(Boat).where(Boat.event_id == event.id).order_by(Boat.number)
            )
        ).scalars()
    )
    existing = list(
        (await session.execute(select(Tracker).where(Tracker.event_id == event.id))).scalars()
    )
    by_boat = {t.boat_id: t for t in existing if t.boat_id is not None}
    by_role = {t.mark_role: t for t in existing if t.mark_role is not None}
    now = datetime.now(UTC)
    created: list[Tracker] = []
    for boat in boats:
        if boat.id not in by_boat:
            created.append(
                Tracker(event_id=event.id, boat_id=boat.id, device_token=_token(), active_from=now)
            )
    if MarkRole.COMMITTEE_BOAT not in by_role:
        created.append(
            Tracker(
                event_id=event.id,
                mark_role=str(MarkRole.COMMITTEE_BOAT),
                device_token=_token(),
                active_from=now,
            )
        )
    session.add_all(created)
    await session.flush()
    return existing + created


def _token() -> str:
    return secrets.token_urlsafe(24)


async def trackers_out(session: AsyncSession, trackers: list[Tracker]) -> list[TrackerOut]:
    boat_ids = [t.boat_id for t in trackers if t.boat_id is not None]
    numbers = (
        dict(
            (await session.execute(select(Boat.id, Boat.number).where(Boat.id.in_(boat_ids)))).all()
        )
        if boat_ids
        else {}
    )
    return sorted(
        (
            TrackerOut(
                id=t.id,
                boat_number=numbers.get(t.boat_id) if t.boat_id is not None else None,
                mark_role=t.mark_role,
                device_token=t.device_token,
                active_from=_aware(t.active_from),
            )
            for t in trackers
        ),
        key=lambda t: (t.boat_number is None, t.boat_number or 0, t.mark_role or ""),
    )


# ------------------------------------------------------------------------- ingest


class UnknownTracker(Exception):
    """No active tracker carries this token."""


async def ingest_fixes(
    session: AsyncSession, token: str, fixes: list[FixIn]
) -> tuple[Tracker, int, int]:
    """Stores a batch; returns the tracker, how many were new and how many it already had.

    Idempotent by ``(tracker, t)``: a phone that retries a batch after a dropped connection
    must not be told off, and must not double the track. The caller commits and publishes.
    """
    now = datetime.now(UTC)
    tracker = (
        await session.execute(select(Tracker).where(Tracker.device_token == token))
    ).scalar_one_or_none()
    if tracker is None or (tracker.active_to is not None and _aware(tracker.active_to) <= now):
        raise UnknownTracker(token)
    times = [f.t for f in fixes]
    known = {
        _aware(t)
        for t in (
            await session.execute(
                select(Fix.t).where(
                    Fix.tracker_id == tracker.id, Fix.t >= min(times), Fix.t <= max(times)
                )
            )
        ).scalars()
    }
    stored = 0
    seen: set[datetime] = set()
    for fix in fixes:
        t = _aware(fix.t)
        if t in known or t in seen:
            continue
        seen.add(t)
        session.add(
            Fix(tracker_id=tracker.id, t=t, lat=fix.lat, lon=fix.lon, sog=fix.sog, cog=fix.cog)
        )
        stored += 1
    await session.flush()
    return tracker, stored, len(fixes) - stored


# --------------------------------------------------------------------- the picture


def _race_info(race: Race, flight: Flight) -> LiveRaceInfo:
    return LiveRaceInfo(
        id=race.id,
        sequence=race.sequence,
        flight=flight.number,
        status=race.status,
        started_at=_aware(race.started_at) if race.started_at else None,
        finished_at=_aware(race.finished_at) if race.finished_at else None,
        signal=race.signal,
    )


async def _race_with_flight(
    session: AsyncSession, event_id: int, status: str
) -> tuple[Race, Flight] | None:
    row = (
        await session.execute(
            select(Race, Flight)
            .join(Flight, Race.flight_id == Flight.id)
            .where(Flight.event_id == event_id, Race.status == status)
            .order_by(Race.sequence)
            .limit(1)
        )
    ).first()
    return (row[0], row[1]) if row else None


#: How long the picture stays on a finished race when nothing is running.
_LINGER = timedelta(minutes=15)


async def _recently_finished(
    session: AsyncSession, event_id: int, now: datetime
) -> tuple[Race, Flight] | None:
    row = (
        await session.execute(
            select(Race, Flight)
            .join(Flight, Race.flight_id == Flight.id)
            .where(
                Flight.event_id == event_id,
                Race.status == RaceStatus.FINISHED,
                Race.finished_at.is_not(None),
                Race.finished_at >= now - _LINGER,
            )
            .order_by(Race.finished_at.desc())
            .limit(1)
        )
    ).first()
    return (row[0], row[1]) if row else None


async def _teams_on_boats(session: AsyncSession, race_id: int) -> dict[int, TeamOut]:
    rows = (
        await session.execute(
            select(Boat.number, Team)
            .join(RaceEntry, RaceEntry.boat_id == Boat.id)
            .join(Team, RaceEntry.team_id == Team.id)
            .options(selectinload(Team.club))
            .where(RaceEntry.race_id == race_id)
        )
    ).all()
    return {
        number: TeamOut(id=team.id, name=team.name, club=ClubOut.model_validate(team.club))
        for number, team in rows
    }


async def live_snapshot(session: AsyncSession, event: Event) -> LiveRaceOut:
    """Everything the live page draws: course, running race, every boat's state and trail."""
    now = datetime.now(UTC)
    course = await active_course(session, event.id)
    running = await _race_with_flight(session, event.id, RaceStatus.RUNNING)
    if running is None:
        # Between races the picture stays on the one just sailed — the boats at the finish,
        # the detected order — until the next gun, rather than going blank.
        running = await _recently_finished(session, event.id, now)
    upcoming = await _race_with_flight(session, event.id, RaceStatus.SCHEDULED)
    race = running[0] if running else None

    trackers = list(
        (
            await session.execute(
                select(Tracker, Boat)
                .join(Boat, Tracker.boat_id == Boat.id)
                .where(Tracker.event_id == event.id)
                .order_by(Boat.number)
            )
        ).all()
    )
    since = (
        _aware(race.started_at) - timedelta(seconds=tracking_settings.emulator_warmup_s + 30)
        if race is not None and race.started_at is not None
        else now - timedelta(minutes=10)
    )
    tracker_ids = [t.id for t, _ in trackers]
    fixes = (
        list(
            (
                await session.execute(
                    select(Fix)
                    .where(Fix.tracker_id.in_(tracker_ids), Fix.t >= since)
                    .order_by(Fix.t)
                )
            ).scalars()
        )
        if tracker_ids
        else []
    )
    by_tracker: dict[int, list[Fix]] = {tid: [] for tid in tracker_ids}
    for fix in fixes:
        by_tracker[fix.tracker_id].append(fix)

    teams = await _teams_on_boats(session, race.id) if race else {}
    ranked = {}
    waypoint_names: list[str] = []
    leg_count: int | None = None
    wind_from: float | None = None
    lines: list[LaylineOut] = []
    leader: list[list[float]] | None = None
    leader_boat: int | None = None
    remaining: dict[int, float] = {}
    if course is not None:
        geometry, projection = course_geometry(course)
        waypoints = geometry.waypoints()
        waypoint_names = [w.name for w in waypoints]
        # Legs are what lies *between* waypoints: start – W – G – W – finish is four legs,
        # so the panel reads 1/4 … 4/4 and then "finished", never 5/5.
        leg_count = len(waypoints) - 1
        wind_from = round(bearing_deg(geometry.axis), 1)
        pipeline = default_pipeline(course_origin(course), tws=course.tws_kn)
        polar = pipeline.ranker.polar  # type: ignore[attr-defined]
        lines = [
            LaylineOut(
                mark=str(line.mark), points=[list(projection.to_geo(p)) for p in line.points]
            )
            for line in laylines(geometry, polar, pipeline.tws)
        ]
    if course is not None and race is not None:
        tracks = {
            boat.number: [
                GeoFix(_aware(f.t), f.lat, f.lon, f.sog, f.cog) for f in by_tracker[tracker.id]
            ]
            for tracker, boat in trackers
        }
        ranked = {r.state.boat: r for r in pipeline.analyse(tracks, geometry)}
        remaining = {
            n: metres_to_go(r.state, waypoints, geometry.axis)
            for n, r in ranked.items()
            if r.finished_at is None
        }
        racing = [
            r for r in ranked.values() if r.finished_at is None and 0 < r.state.leg <= leg_count
        ]
        if racing and race.status == RaceStatus.RUNNING:
            first = min(racing, key=lambda r: r.rank)
            ends = leader_line(
                first.state.position,
                waypoints[first.state.leg],
                geometry.axis,
                tracking_settings.leader_line_half_m,
            )
            leader = [list(projection.to_geo(p)) for p in ends]
            leader_boat = first.state.boat
    leader_remaining = min(remaining.values(), default=None)

    boats: list[LiveBoatOut] = []
    trail_from = now - timedelta(seconds=tracking_settings.trail_seconds)
    for tracker, boat in trackers:
        track = by_tracker[tracker.id]
        if not track:
            continue
        last = track[-1]
        trail = [f for f in track if _aware(f.t) >= trail_from]
        step = max(1, len(trail) // 30)
        r = ranked.get(boat.number)
        leg = r.state.leg if r else None
        boats.append(
            LiveBoatOut(
                boat_number=boat.number,
                color=boat.color,
                team=teams.get(boat.number),
                t=_aware(last.t),
                lat=last.lat,
                lon=last.lon,
                sog_kn=round(last.sog / KNOT, 2),
                cog=round(last.cog, 1),
                leg=leg,
                leg_name=(
                    waypoint_names[leg]
                    if leg is not None and leg < len(waypoint_names)
                    else ("finished" if leg is not None else None)
                ),
                to_go_m=round(r.state.to_go, 1) if r else None,
                time_to_go_s=round(r.time_to_go, 1) if r and r.time_to_go is not None else None,
                to_leader_m=(
                    round(remaining[boat.number] - leader_remaining, 1)
                    if boat.number in remaining and leader_remaining is not None
                    else None
                ),
                rank=r.rank if r else None,
                finished_at=r.finished_at if r else None,
                trail=[[f.lat, f.lon] for f in trail[::step]],
            )
        )
    finished = sorted(
        (b for b in boats if b.finished_at is not None),
        key=lambda b: b.finished_at,  # type: ignore[arg-type, return-value]
    )
    return LiveRaceOut(
        event_id=event.id,
        course=course_out(course) if course else None,
        leg_count=leg_count,
        wind_from_deg=wind_from,
        laylines=lines,
        leader_line=leader,
        leader_boat=leader_boat,
        race=_race_info(*running) if running else None,
        next_race=_race_info(*upcoming) if upcoming else None,
        boats=boats,
        detected_finish_order=[b.boat_number for b in finished],
        boat_length_m=tracking_settings.boat_length_m,
        boat_beam_m=tracking_settings.boat_beam_m,
        zone_radius_m=tracking_settings.zone_radius_m,
        t=now,
    )


async def publish_positions(session: AsyncSession, event: Event) -> LiveRaceOut:
    """The inline payload of Story B-5: positions travel in the stream, not as a token."""
    snapshot = await live_snapshot(session, event)
    hub.send(event_topic(event.id), "positions", snapshot.model_dump(mode="json"))
    return snapshot

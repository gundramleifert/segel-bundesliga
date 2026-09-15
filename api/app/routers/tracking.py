"""Tracking endpoints — Stories L-1, L-2.

Three groups: the committee lays the course and issues trackers (admin, race officer);
phones post fixes with their tracker token (no other auth — the token *is* the identity of
a device on a boat); spectators read the live picture of a published event.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_race_officer
from app.db import get_session
from app.live import event_topic, hub
from app.models import Event
from app.problems import Problem
from app.routers.public import _only_public_events
from app.schemas.tracking import (
    CourseIn,
    CourseOut,
    DefaultCourseIn,
    FixBatchIn,
    FixBatchOut,
    LiveRaceOut,
    TrackerOut,
)
from app.tracking import service

admin_router = APIRouter(
    prefix="/api/admin/events/{event_id}",
    tags=["tracking"],
    dependencies=[Depends(require_race_officer)],
)
router = APIRouter(prefix="/api", tags=["tracking"])


async def _event(session: AsyncSession, event_id: int) -> Event:
    event = await session.get(Event, event_id)
    if event is None:
        raise Problem(404, "event-not-found", f"Event {event_id} not found.")
    return event


@admin_router.get("/course", response_model=CourseOut, summary="The course as laid")
async def get_event_course(
    event_id: int, session: AsyncSession = Depends(get_session)
) -> CourseOut:
    event = await _event(session, event_id)
    course = await service.active_course(session, event.id)
    if course is None:
        raise Problem(404, "course-not-laid", "No course has been laid for this event yet.")
    return service.course_out(course)


@admin_router.put("/course", response_model=CourseOut, summary="Lay the course")
async def lay_event_course(
    event_id: int, request: CourseIn, session: AsyncSession = Depends(get_session)
) -> CourseOut:
    """Six marks as the committee set them. A re-lay is a new course; races already
    started keep the one they were started on."""
    event = await _event(session, event_id)
    course = await service.store_course(session, event, request)
    await session.commit()
    hub.publish(event_topic(event.id))
    return service.course_out(await service.active_course(session, event.id) or course)


@admin_router.post(
    "/course/default", response_model=CourseOut, summary="Lay the textbook course here"
)
async def lay_default_event_course(
    event_id: int,
    request: DefaultCourseIn | None = None,
    session: AsyncSession = Depends(get_session),
) -> CourseOut:
    """A windward/leeward course around the venue (or the given point), square to the
    given wind — the emulator's course, and a committee's starting point to drag from."""
    event = await _event(session, event_id)
    await service.lay_default_course(session, event, request or DefaultCourseIn())
    await session.commit()
    hub.publish(event_topic(event.id))
    course = await service.active_course(session, event.id)
    assert course is not None
    return service.course_out(course)


@admin_router.get("/trackers", response_model=list[TrackerOut], summary="The event's trackers")
async def list_event_trackers(
    event_id: int, session: AsyncSession = Depends(get_session)
) -> list[TrackerOut]:
    """One per boat plus the committee boat, issued on first call. The tokens are what a
    phone sends with every batch; show them as QR codes, never type them."""
    event = await _event(session, event_id)
    trackers = await service.ensure_trackers(session, event)
    await session.commit()
    return await service.trackers_out(session, trackers)


@router.post("/track/fixes", response_model=FixBatchOut, summary="Post a batch of fixes")
async def post_fixes(
    request: FixBatchIn, session: AsyncSession = Depends(get_session)
) -> FixBatchOut:
    """What a phone on a boat sends every few seconds (Story L-4), and what the emulator
    sends. Idempotent: a retried batch stores nothing twice and is not an error."""
    try:
        tracker, stored, duplicates = await service.ingest_fixes(
            session, request.token, request.fixes
        )
    except service.UnknownTracker as exc:
        raise Problem(401, "tracker-unknown", "No active tracker carries this token.") from exc
    await session.commit()
    if stored:
        event = await session.get(Event, tracker.event_id)
        assert event is not None
        await service.publish_positions(session, event)
    return FixBatchOut(stored=stored, duplicates=duplicates)


@router.get("/events/{event_id}/live", response_model=LiveRaceOut, summary="The boats now")
async def get_event_live(
    event_id: int, session: AsyncSession = Depends(get_session)
) -> LiveRaceOut:
    """The course, the running race, every boat's position, speed, leg and rank — Story L-1.

    Published events only, by the public router's own predicate; a draft answers 404 here
    exactly as it does everywhere else.
    """
    event = (
        await session.execute(_only_public_events(select(Event).where(Event.id == event_id)))
    ).scalar_one_or_none()
    if event is None:
        raise Problem(404, "event-not-found", f"Event {event_id} not found.")
    return await service.live_snapshot(session, event)

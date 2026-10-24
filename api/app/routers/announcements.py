"""Publishing on an event's notice board — Story VA-11.

The race committee, the jury and the organizer each speak for themselves: a request names
its issuer, and the person must hold that issuer's relation on the event
(``app/services/announcements.py``). Reading is public, next to the event's documents
(``app/routers/public.py``).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import forbidden, require_on_event
from app.db import get_session
from app.live import event_topic, hub
from app.models import AnnouncementIssuer, Event, EventAnnouncement, Relation, User
from app.problems import Problem
from app.routers.public import announcement_out
from app.schemas.public import AnnouncementOut
from app.services.announcements import ISSUER_RELATION, may_announce_as
from app.services.lookup import get_or_404

router = APIRouter(prefix="/api/admin/events", tags=["administration"])

# Whoever may announce as anyone passes the gate; the issuer is checked in the handler.
require_announcer = require_on_event(Relation.MANAGER, Relation.RACE_OFFICER, Relation.JURY)


class AnnouncementIn(BaseModel):
    issuer: AnnouncementIssuer = Field(
        description="Whom the announcement speaks for; the person must hold that relation."
    )
    # No ``min_length``: an empty title and a blank one get the same typed answer, which
    # the handler gives once the text is stripped.
    title: str = Field(max_length=200)
    body: str = Field(default="", max_length=4000)

    @field_validator("title", "body")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


def _require_issuer(user: User, issuer: AnnouncementIssuer, event: Event) -> None:
    if not may_announce_as(user, issuer, event):
        raise forbidden(
            f"announcing as the {issuer.value.replace('_', ' ')}", [ISSUER_RELATION[issuer]]
        )


@router.post(
    "/{event_id}/announcements",
    response_model=AnnouncementOut,
    status_code=status.HTTP_201_CREATED,
    summary="Publish an announcement on the event's notice board",
)
async def publish_announcement(
    event_id: int,
    body: AnnouncementIn,
    user: User = Depends(require_announcer),
    session: AsyncSession = Depends(get_session),
) -> AnnouncementOut:
    """Story VA-11: it appears at once on the event's public page and in the live view."""
    event = await get_or_404(session, Event, event_id)
    _require_issuer(user, body.issuer, event)
    if not body.title:
        raise Problem(422, "announcement-title-empty", "An announcement needs a title.")
    # The next number is counted in the INSERT itself, so two notices published at once
    # cannot read the same highest one; the unique constraint backs that up.
    next_number = (
        select(func.coalesce(func.max(EventAnnouncement.number), 0) + 1)
        .where(EventAnnouncement.event_id == event.id)
        .scalar_subquery()
    )
    announcement = EventAnnouncement(
        event_id=event.id,
        number=next_number,
        issuer=body.issuer,
        title=body.title,
        body=body.body,
        author_id=user.id,
    )
    session.add(announcement)
    await session.commit()
    await session.refresh(announcement)
    # After the commit (Story B-5): an open notice board refetches and finds it.
    hub.publish(event_topic(event.id))
    announcement.author = user
    return announcement_out(announcement)


@router.delete(
    "/{event_id}/announcements/{announcement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Retract an announcement",
)
async def retract_announcement(
    event_id: int,
    announcement_id: int,
    user: User = Depends(require_announcer),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Story VA-11: whoever may announce as its issuer may take it back — a wrong time
    is corrected by retracting it and publishing the right one."""
    event = await get_or_404(session, Event, event_id)
    announcement = await session.get(EventAnnouncement, announcement_id)
    if announcement is None or announcement.event_id != event.id:
        raise Problem(404, "announcement-not-found", "No such announcement on this event.")
    _require_issuer(user, AnnouncementIssuer(announcement.issuer), event)
    await session.delete(announcement)
    await session.commit()
    hub.publish(event_topic(event.id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)

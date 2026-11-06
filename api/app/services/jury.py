"""The league's pool of judges, and who sits on which jury (Stories JU-1–JU-5).

Two tuples carry the facts the rest of the site reads: ``user:judge:site`` — in the pool —
and ``user:jury:event`` — on that event's jury, which is what opens the event in the
judge's space, its notice board and an expense claim on it (F-2). Both are written here
through `app/services/grants.py`, never by hand. :class:`JuryRequest` is the conversation
before an approval; ``approved`` on it is kept in step with the event's tuple.

Nothing here commits or mails: the router commits, then mails — a mail about a row that
did not land would be a mail about nothing.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import authz
from app.models import Event, EventStatus, JudgeLicence, JudgeLicenceHolding, JuryRequest
from app.models.auth import ObjectRef, ObjectType, Relation, User
from app.models.base import utcnow
from app.problems import Problem
from app.services import grants

#: An event in one of these states takes no more asking or approving.
CLOSED = frozenset({EventStatus.FINAL, EventStatus.CANCELLED})


def is_judge(user: User) -> bool:
    """In the pool — the tuple itself, so a site admin is not a judge by being admin."""
    return authz.read(user, Relation.JUDGE)


def not_a_judge(user_ids: Iterable[int]) -> Problem:
    return Problem(
        422,
        "not-a-judge",
        "Only judges from the pool can be asked or put on a jury.",
        user_ids=sorted(user_ids),
    )


async def _users(session: AsyncSession, user_ids: Iterable[int]) -> dict[int, User]:
    wanted = set(user_ids)
    found = {
        u.id: u for u in (await session.execute(select(User).where(User.id.in_(wanted)))).scalars()
    }
    if missing := wanted - set(found):
        raise Problem(404, "user-not-found", "No such account.", user_ids=sorted(missing))
    return found


async def judges(session: AsyncSession, user_ids: Iterable[int]) -> dict[int, User]:
    """These accounts, each a judge — else ``not-a-judge`` naming those who are not."""
    users = await _users(session, user_ids)
    if outside := [i for i, u in users.items() if not is_judge(u)]:
        raise not_a_judge(outside)
    return users


async def open_events(session: AsyncSession, event_ids: Iterable[int]) -> list[Event]:
    """These events, none of them over — else ``jury-event-closed``."""
    wanted = set(event_ids)
    events = list(
        (await session.execute(select(Event).where(Event.id.in_(wanted)).order_by(Event.starts_on, Event.id))).scalars()
    )
    if missing := wanted - {e.id for e in events}:
        raise Problem(404, "event-not-found", "No such event.", event_ids=sorted(missing))
    if closed := [e.id for e in events if e.status in CLOSED]:
        raise Problem(
            409,
            "jury-event-closed",
            "This event is over; its jury is no longer staffed here.",
            event_ids=closed,
        )
    return events


# ---------------------------------------------------------------- the pool (JU-1, JU-2)


async def add_judge(session: AsyncSession, user_id: int, *, actor: User) -> User:
    user = (await _users(session, [user_id]))[user_id]
    await grants.grant(session, user, Relation.JUDGE, ObjectType.SITE, None, actor=actor)
    return user


async def remove_judge(session: AsyncSession, user_id: int, *, actor: User) -> None:
    """Out of the pool; their open requests go with them, an approved event stays."""
    user = (await _users(session, [user_id]))[user_id]
    row = next(
        (g for g in user.grants if g.relation == Relation.JUDGE and g.object_type is ObjectType.SITE),
        None,
    )
    if row is None:
        raise not_a_judge([user_id])
    await grants.revoke(session, user, row, actor=actor)
    await session.execute(
        delete(JuryRequest).where(JuryRequest.user_id == user_id, JuryRequest.approved.is_(False))
    )


async def licences_of(session: AsyncSession, user_ids: Iterable[int]) -> dict[int, list[JudgeLicence]]:
    out: dict[int, list[JudgeLicence]] = {}
    rows = await session.execute(
        select(JudgeLicenceHolding)
        .where(JudgeLicenceHolding.user_id.in_(set(user_ids)))
        .order_by(JudgeLicenceHolding.licence)
    )
    for row in rows.scalars():
        out.setdefault(row.user_id, []).append(JudgeLicence(row.licence))
    return out


async def set_licences(session: AsyncSession, user: User, licences: Iterable[JudgeLicence]) -> None:
    """The judge's own word (JU-2): exactly these, replacing what was said before."""
    if not is_judge(user):
        raise Problem(403, "not-a-judge", "Only a judge states their licences.")
    await session.execute(delete(JudgeLicenceHolding).where(JudgeLicenceHolding.user_id == user.id))
    session.add_all(JudgeLicenceHolding(user_id=user.id, licence=str(lic)) for lic in set(licences))


# ---------------------------------------------------------------- asking (JU-3)


@dataclass
class Asked:
    """One judge's newly asked events — what their one mail names."""

    user: User
    events: list[Event] = field(default_factory=list)


@dataclass
class Invited:
    created: int
    existing: int
    asked: list[Asked]


async def invite(session: AsyncSession, event_ids: Sequence[int], user_ids: Sequence[int]) -> Invited:
    """Events × judges; a pair asked before is left as it was."""
    events = await open_events(session, event_ids)
    users = await judges(session, user_ids)
    existing = {
        (r.event_id, r.user_id)
        for r in (
            await session.execute(
                select(JuryRequest).where(
                    JuryRequest.event_id.in_([e.id for e in events]),
                    JuryRequest.user_id.in_(list(users)),
                )
            )
        ).scalars()
    }
    now = utcnow()
    asked: dict[int, Asked] = {}
    for user in users.values():
        for event in events:
            if (event.id, user.id) in existing:
                continue
            session.add(JuryRequest(event_id=event.id, user_id=user.id, invited_at=now))
            asked.setdefault(user.id, Asked(user)).events.append(event)
    created = sum(len(a.events) for a in asked.values())
    return Invited(created=created, existing=len(existing), asked=list(asked.values()))


# ---------------------------------------------------------------- answering (JU-4)


async def request_of(session: AsyncSession, event_id: int, user_id: int) -> JuryRequest | None:
    return (
        await session.execute(
            select(JuryRequest)
            .options(selectinload(JuryRequest.event))
            .where(JuryRequest.event_id == event_id, JuryRequest.user_id == user_id)
        )
    ).scalar_one_or_none()


async def answer(session: AsyncSession, user: User, event_id: int, *, available: bool) -> JuryRequest:
    request = await request_of(session, event_id, user.id)
    if request is None:
        raise Problem(404, "jury-request-not-found", "Nobody asked you for this event.")
    if request.approved:
        raise Problem(
            409,
            "jury-already-approved",
            "You are on this event's jury; ask the jury organizer to take you off.",
        )
    request.available = available
    request.answered_at = utcnow()
    return request


async def requests_of(session: AsyncSession, user_id: int) -> list[JuryRequest]:
    """Mine, the next event first."""
    rows = await session.execute(
        select(JuryRequest)
        .join(Event, Event.id == JuryRequest.event_id)
        .options(selectinload(JuryRequest.event))
        .where(JuryRequest.user_id == user_id)
        .order_by(Event.starts_on.is_(None), Event.starts_on, Event.id)
    )
    return list(rows.scalars())


async def unanswered(session: AsyncSession, user_id: int) -> int:
    """The judge's to-do (``jury_invited``): asked, not answered, the event not over."""
    rows = await session.execute(
        select(JuryRequest.id)
        .join(Event, Event.id == JuryRequest.event_id)
        .where(
            JuryRequest.user_id == user_id,
            JuryRequest.invited_at.is_not(None),
            JuryRequest.available.is_(None),
            JuryRequest.approved.is_(False),
            Event.status.not_in(CLOSED),
        )
    )
    return len(rows.all())


# ---------------------------------------------------------------- approving (JU-5)


async def approve(session: AsyncSession, event_id: int, user_id: int, *, actor: User) -> JuryRequest:
    """On the event's jury — from any state, or with no request at all."""
    (event,) = await open_events(session, [event_id])
    user = (await judges(session, [user_id]))[user_id]
    request = await request_of(session, event_id, user_id)
    if request is None:
        request = JuryRequest(event_id=event_id, user_id=user_id)
        request.event = event
        session.add(request)
    request.approved = True
    request.decided_at = utcnow()
    if not authz.read(user, Relation.JURY, ObjectRef(ObjectType.EVENT, event_id)):
        await grants.grant(session, user, Relation.JURY, ObjectType.EVENT, event_id, actor=actor)
    return request


async def take_off(session: AsyncSession, event_id: int, user_id: int, *, actor: User) -> JuryRequest:
    """Off the event's jury: the tuple goes, the judge's answer stays."""
    user = (await _users(session, [user_id]))[user_id]
    request = await request_of(session, event_id, user_id)
    if request is None or not request.approved:
        raise Problem(404, "jury-request-not-found", "This judge is not on this event's jury.")
    request.approved = False
    request.decided_at = utcnow()
    row = next(
        (g for g in user.grants if g.relation == Relation.JURY and g.event_id == event_id),
        None,
    )
    if row is not None:
        await grants.revoke(session, user, row, actor=actor)
    if request.invited_at is None and request.available is None:
        # Put on directly and taken off again: nothing was ever asked or answered.
        await session.delete(request)
    return request

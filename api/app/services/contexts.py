"""Story Z-8: every club, series and event a person is part of, and what waits for them.

The one answer to "which clubs, series and events are mine". The account page, the club
screen and the reimbursements page each used to compute their own, and the three
disagreed — a club's treasurer had no club, a helper no event, and sailing was nowhere,
because a squad or a crew is not a tuple.

**Part of** is therefore two sources, merged per object:

* a **relation** held directly on a club, series or event (Story Z-2). Only direct tuples:
  a host club's manager *may* act on each of its events through the model, but the club
  is where they look, and listing every event they could reach would bury the ones they
  were actually named for. Site relations are not "mine" either — that is `/admin`.
* **sailing** — a place in a series' squad, or in an event's crew (Stories V-1, V-2),
  reported as the pseudo-relation ``sailor``.

**Needs** are counts with a code, never sentences — the page words them (i18n).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Club, Event, PersonalDocument, Sailor, Series, Team, TeamMembership
from app.models.auth import ObjectType, User
from app.models.competition import EventStatus
from app.models.org import TeamStatus
from app.services import expenses
from app.services.waivers import (
    STATUS_CLEARED,
    STATUS_NOT_REQUIRED,
    event_waiver_status,
    sailor_competitions,
    series_waiver_status,
)

#: The chips, in reading order: what I *am* there, then what I *do* there.
SAILOR = "sailor"
RELATION_ORDER = [
    "member",
    SAILOR,
    "admin",
    "manager",
    "treasurer",
    "race_officer",
    "jury",
    "helper",
]

KIND_OF = {ObjectType.CLUB: "club", ObjectType.SERIES: "series", ObjectType.EVENT: "event"}


@dataclass
class Need:
    code: str
    count: int


@dataclass
class TeamRef:
    """A team I sail in — the squad of a series, or the crew of an event."""

    team_id: int
    club_id: int
    club_name: str


@dataclass
class Context:
    kind: str
    id: int
    name: str
    relations: set[str] = field(default_factory=set)
    needs: dict[str, int] = field(default_factory=dict)
    teams: list[TeamRef] = field(default_factory=list)
    short_name: str | None = None
    starts_on: date | None = None
    ends_on: date | None = None
    status: str | None = None
    published: bool = True
    series_id: int | None = None
    year: int | None = None

    def need(self, code: str, count: int = 1) -> None:
        self.needs[code] = self.needs.get(code, 0) + count

    @property
    def ordered_relations(self) -> list[str]:
        return sorted(self.relations, key=RELATION_ORDER.index)

    @property
    def ordered_needs(self) -> list[Need]:
        return [Need(code, count) for code, count in self.needs.items() if count]


@dataclass
class MySpace:
    name: str
    needs: list[Need]
    contexts: list[Context]


async def linked_sailor(session: AsyncSession, user: User) -> Sailor | None:
    """The sailor record under this account's **verified** address — the same rule as the
    profile (`routers/sailors.py::_my_sailor`), without its 404: having no sailor record is
    a normal answer here."""
    if not user.email_verified:
        return None
    return (
        await session.execute(select(Sailor).where(Sailor.email == user.email.lower()))
    ).scalar_one_or_none()


async def my_space(session: AsyncSession, user: User) -> MySpace:
    contexts: dict[tuple[str, int], Context] = {}

    def at(kind: str, object_id: int) -> Context:
        key = (kind, object_id)
        if key not in contexts:
            contexts[key] = Context(kind=kind, id=object_id, name="")
        return contexts[key]

    for grant in user.grants:
        kind = KIND_OF.get(grant.object_type)
        if kind is not None and grant.object_id is not None:
            at(kind, grant.object_id).relations.add(grant.relation)

    sailor = await linked_sailor(session, user)
    if sailor is not None:
        await _sailing(session, sailor, at)
        await _waivers(session, sailor, at)

    await _fill(session, contexts)
    _claims(await expenses.pending(session, user), contexts)
    await _organizer(session, user, contexts)

    me_needs = []
    expired = await _expired_documents(session, user)
    if expired:
        me_needs.append(Need("documents_expired", expired))

    return MySpace(
        name=sailor.full_name if sailor is not None else user.display_name,
        needs=me_needs,
        contexts=sorted(contexts.values(), key=_order),
    )


async def _sailing(session: AsyncSession, sailor: Sailor, at) -> None:
    """A squad is a series registration (no event), a crew an event entry (Story V-1)."""
    rows = (
        await session.execute(
            select(Team.id, Team.series_id, Team.event_id, Club.id, Club.name)
            .join(TeamMembership, TeamMembership.team_id == Team.id)
            .join(Club, Team.club_id == Club.id)
            .where(TeamMembership.sailor_id == sailor.id, Team.status == TeamStatus.ACCEPTED)
            .order_by(Club.name)
        )
    ).all()
    for team_id, series_id, event_id, club_id, club_name in rows:
        context = at("event", event_id) if event_id is not None else at("series", series_id)
        context.relations.add(SAILOR)
        context.teams.append(TeamRef(team_id, club_id, club_name))


async def _waivers(session: AsyncSession, sailor: Sailor, at) -> None:
    """Where the signature is asked for — the series, or an event in no series (S-1)."""
    for competition in await sailor_competitions(session, sailor):
        if competition.series is not None:
            judged = await series_waiver_status(session, competition.series, sailor)
        else:
            assert competition.event is not None
            judged = (await event_waiver_status(session, competition.event, [sailor.id]))[sailor.id]
        if judged.status not in (STATUS_CLEARED, STATUS_NOT_REQUIRED):
            at(competition.scope, competition.scope_id).need("waiver")


async def _fill(session: AsyncSession, contexts: dict[tuple[str, int], Context]) -> None:
    """Names and dates, one query per kind."""

    def ids(kind: str) -> list[int]:
        return [object_id for (k, object_id) in contexts if k == kind]

    if club_ids := ids("club"):
        for club in (await session.execute(select(Club).where(Club.id.in_(club_ids)))).scalars():
            context = contexts[("club", club.id)]
            context.name, context.short_name = club.name, club.short_name
    if series_ids := ids("series"):
        rows = (await session.execute(select(Series).where(Series.id.in_(series_ids)))).scalars()
        for series in rows:
            context = contexts[("series", series.id)]
            context.name, context.short_name = series.name, series.short_name
            context.starts_on, context.ends_on = series.starts_on, series.ends_on
            context.year, context.published = series.year, series.published
    if event_ids := ids("event"):
        for event in (
            await session.execute(select(Event).where(Event.id.in_(event_ids)))
        ).scalars():
            context = contexts[("event", event.id)]
            context.name = event.title
            context.starts_on, context.ends_on = event.starts_on, event.ends_on
            context.status, context.published = event.status, event.published
            context.series_id = event.series_id
    # A tuple on an object that has since gone is nobody's context.
    for key in [key for key, context in contexts.items() if not context.name]:
        del contexts[key]


def _claims(pending: list, contexts: dict[tuple[str, int], Context]) -> None:
    """Each claim waiting for me, on the card I would open to deal with it: the event when
    I hold the event, else the club that pays (Story F-6)."""
    for claim in pending:
        for key in (
            ("event", claim.event_id),
            ("club", claim.payer_club_id),
            ("club", claim.club_id),
        ):
            if key[1] is not None and key in contexts:
                contexts[key].need("claims")
                break


async def _organizer(
    session: AsyncSession, user: User, contexts: dict[tuple[str, int], Context]
) -> None:
    """What only a club's organizer can fix: a running series' squad below its minimum,
    an upcoming entry with nobody named (Stories V-1, V-2)."""
    clubs = [club_id for club_id in user.managed_club_ids if ("club", club_id) in contexts]
    if not clubs:
        return
    today = date.today()
    size = (
        select(func.count(TeamMembership.id))
        .where(TeamMembership.team_id == Team.id)
        .correlate(Team)
        .scalar_subquery()
    )
    short = (
        await session.execute(
            select(Team.club_id)
            .join(Series, Team.series_id == Series.id)
            .where(
                Team.club_id.in_(clubs),
                Team.event_id.is_(None),
                Team.status == TeamStatus.ACCEPTED,
                (Series.ends_on.is_(None)) | (Series.ends_on >= today),
                size < Series.squad_min,
            )
        )
    ).scalars()
    for club_id in short:
        contexts[("club", club_id)].need("squad_below_min")
    uncrewed = (
        await session.execute(
            select(Team.club_id)
            .join(Event, Team.event_id == Event.id)
            .where(
                Team.club_id.in_(clubs),
                Team.status == TeamStatus.ACCEPTED,
                Event.status == EventStatus.PLANNED,
                Event.starts_on >= today,
                size == 0,
            )
        )
    ).scalars()
    for club_id in uncrewed:
        contexts[("club", club_id)].need("crew_missing")


async def _expired_documents(session: AsyncSession, user: User) -> int:
    return (
        await session.execute(
            select(func.count(PersonalDocument.id)).where(
                PersonalDocument.user_id == user.id,
                PersonalDocument.valid_until < date.today(),
            )
        )
    ).scalar_one()


def _order(context: Context) -> tuple:
    """Clubs by name, series newest year first, events by date (undated last)."""
    kind = ["club", "series", "event"].index(context.kind)
    if context.kind == "series":
        return (kind, -(context.year or 0), context.name.lower())
    if context.kind == "event":
        return (
            kind,
            context.starts_on is None,
            context.starts_on or date.min,
            context.name.lower(),
        )
    return (kind, context.name.lower())

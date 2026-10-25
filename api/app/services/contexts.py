"""Stories Z-8, Z-10: every club, series and event a person is part of, and what waits.

The one answer to "which clubs, series and events are mine". The account page, the club
screen and the reimbursements page each used to compute their own, and the three
disagreed — a club's treasurer had no club, a helper no event, and sailing was nowhere,
because a squad or a crew is not a tuple.

**Part of** is therefore two sources, merged per object:

* a **relation** held directly on a club, series or event (Story Z-2). Only direct tuples:
  a host club's manager *may* act on each of its events through the model, but the club
  is where they look, and listing every event they could reach would bury the ones they
  were actually named for. Site relations are not "mine" either — they are the league
  **office**, reported beside the contexts, not among them (Story Z-10).
* **sailing** — a place in a series' squad, or in an event's crew (Stories V-1, V-2),
  reported as the pseudo-relation ``sailor``.

**Needs** are counts with a code, never sentences — the page words them (i18n). Each
names the **section** that clears it and a **severity** (Story Z-10, the plan's §4), and
appears only for whoever holds that section — asked of the model (`app/authz.py`), never
of a summary role. Computed on every request, never stored: something no longer true is
no longer listed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import StrEnum

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import authz
from app.models import (
    Club,
    Event,
    EventCrew,
    Flight,
    Grant,
    ImportRun,
    Payment,
    PaymentRun,
    PersonalDocument,
    Race,
    RaceEntry,
    Sailor,
    SailorClub,
    Series,
    Team,
    TeamMembership,
    WaiverText,
)
from app.models.auth import ObjectType, Relation, User
from app.models.competition import EventStatus
from app.models.finance import PaymentStatus
from app.models.org import TeamStatus
from app.models.racing import RaceStatus
from app.problems import Problem
from app.services import expenses
from app.services.event_readiness import event_readiness
from app.services.waivers import (
    WaiverStatus,
    current_waiver_text,
    event_waiver_status,
    is_minor,
    sailor_waivers,
)


class ContextRelation(StrEnum):
    """What I am to a context — a tuple's relation, or ``sailor`` for a squad or a crew.
    Declared in reading order: what I *am* there, then what I *do* there."""

    MEMBER = "member"
    SAILOR = "sailor"
    ADMIN = "admin"
    MANAGER = "manager"
    EDITOR = "editor"
    TREASURER = "treasurer"
    RACE_OFFICER = "race_officer"
    JURY = "jury"
    HELPER = "helper"


SAILOR = ContextRelation.SAILOR
#: The chips, in reading order.
RELATION_ORDER = list(ContextRelation)


class NeedCode(StrEnum):
    """What waits — the page words it as ``needs.<code>``."""

    WAIVER = "waiver"
    WARD_WAIVER = "ward_waiver"
    DOCUMENTS_EXPIRED = "documents_expired"
    CLAIM_REJECTED = "claim_rejected"
    CLAIMS = "claims"
    SQUAD_BELOW_MIN = "squad_below_min"
    CREW_MISSING = "crew_missing"
    CREW_WAIVER_MISSING = "crew_waiver_missing"
    MINOR_WITHOUT_GUARDIAN = "minor_without_guardian"
    SAILOR_WITHOUT_BIRTH_DATE = "sailor_without_birth_date"
    PAYMENT_RUN_OPEN = "payment_run_open"
    EVENT_NOT_READY = "event_not_ready"
    EVENT_UNPUBLISHED = "event_unpublished"
    CHECKIN_WAIVERS_MISSING = "checkin_waivers_missing"
    RESULTS_MISSING = "results_missing"
    REGISTRATIONS_OPEN = "registrations_open"
    CLUBS_WITHOUT_LEAGUE = "clubs_without_league"
    IMPORTS_FAILED = "imports_failed"


class Section(StrEnum):
    """The sidebar's section keys (Story Z-10, the declaration of #30) — every key of
    every context kind, since a need links to one of them."""

    OVERVIEW = "overview"
    # Me
    ACCOUNT = "account"
    WAIVERS = "waivers"
    CLAIMS = "claims"
    DOCUMENTS = "documents"
    BANK = "bank"
    CHILDREN = "children"
    # Club
    MEMBERS = "members"
    SAILORS = "sailors"
    MINORS = "minors"
    SQUADS = "squads"
    CREWS = "crews"
    HOSTING = "hosting"
    MY_CLAIMS = "my-claims"
    DECIDE_CLAIMS = "decide-claims"
    PAYMENT_RUNS = "payment-runs"
    BANK_ACCOUNT = "bank-account"
    CLUB_PAGE = "club-page"
    # Series
    TEAM = "team"
    EVENTS = "events"
    STANDINGS = "standings"
    REGISTRATIONS = "registrations"
    DATES = "dates"
    SCORING = "scoring"
    OFFICIALS = "officials"
    NEWS = "news"
    # Event
    CREW = "crew"
    GENERAL = "general"
    CLUBS = "clubs"
    BOATS = "boats"
    PAIRING = "pairing"
    PUBLICATION = "publication"
    PEOPLE = "people"
    CHECK_IN = "check-in"
    RACE_CONTROL = "race-control"
    RESULTS = "results"
    TRACKERS = "trackers"
    NOTICE_BOARD = "notice-board"
    # League office
    SERIES = "series"
    ACCOUNTS = "accounts"
    MEDIA = "media"
    IMPORTS = "imports"


class Severity(StrEnum):
    """How soon (Story Z-10): orders the to-dos, it does not shout."""

    NOW = "now"
    SOON = "soon"
    INFO = "info"


#: Where each need is cleared, per kind of card it sits on.
SECTION_OF: dict[tuple[str, NeedCode], Section] = {
    ("me", NeedCode.WAIVER): Section.WAIVERS,
    ("series", NeedCode.WAIVER): Section.TEAM,
    ("event", NeedCode.WAIVER): Section.CREW,
    ("me", NeedCode.WARD_WAIVER): Section.CHILDREN,
    ("me", NeedCode.DOCUMENTS_EXPIRED): Section.DOCUMENTS,
    ("me", NeedCode.CLAIM_REJECTED): Section.CLAIMS,
    ("club", NeedCode.CLAIM_REJECTED): Section.MY_CLAIMS,
    ("event", NeedCode.CLAIM_REJECTED): Section.MY_CLAIMS,
    ("club", NeedCode.CLAIMS): Section.DECIDE_CLAIMS,
    ("event", NeedCode.CLAIMS): Section.DECIDE_CLAIMS,
    ("club", NeedCode.SQUAD_BELOW_MIN): Section.SQUADS,
    ("club", NeedCode.CREW_MISSING): Section.CREWS,
    ("club", NeedCode.CREW_WAIVER_MISSING): Section.WAIVERS,
    ("club", NeedCode.MINOR_WITHOUT_GUARDIAN): Section.MINORS,
    ("club", NeedCode.SAILOR_WITHOUT_BIRTH_DATE): Section.SAILORS,
    ("club", NeedCode.PAYMENT_RUN_OPEN): Section.PAYMENT_RUNS,
    ("event", NeedCode.EVENT_NOT_READY): Section.OVERVIEW,
    ("event", NeedCode.EVENT_UNPUBLISHED): Section.PUBLICATION,
    ("series", NeedCode.EVENT_UNPUBLISHED): Section.DATES,
    ("event", NeedCode.CHECKIN_WAIVERS_MISSING): Section.CHECK_IN,
    ("event", NeedCode.RESULTS_MISSING): Section.RESULTS,
    ("series", NeedCode.REGISTRATIONS_OPEN): Section.REGISTRATIONS,
    ("event", NeedCode.REGISTRATIONS_OPEN): Section.CLUBS,
    ("office", NeedCode.CLUBS_WITHOUT_LEAGUE): Section.CLUBS,
    ("office", NeedCode.IMPORTS_FAILED): Section.IMPORTS,
}

#: Race day itself: the check-in and the results are always *now*.
ALWAYS_NOW = {NeedCode.CHECKIN_WAIVERS_MISSING, NeedCode.RESULTS_MISSING}
#: Undated, but someone waits on it — *soon*; every other undated need is *info*.
WAITED_ON = {
    NeedCode.WAIVER,
    NeedCode.WARD_WAIVER,
    NeedCode.DOCUMENTS_EXPIRED,
    NeedCode.CLAIM_REJECTED,
    NeedCode.CLAIMS,
    NeedCode.SQUAD_BELOW_MIN,
    NeedCode.MINOR_WITHOUT_GUARDIAN,
    NeedCode.SAILOR_WITHOUT_BIRTH_DATE,
    NeedCode.REGISTRATIONS_OPEN,
    NeedCode.IMPORTS_FAILED,
}
#: A race day this close makes what it needs *now*; this close, *soon*.
NOW_WITHIN = timedelta(days=7)
SOON_WITHIN = timedelta(days=30)
SEVERITY_ORDER = list(Severity)

KIND_OF = {ObjectType.CLUB: "club", ObjectType.SERIES: "series", ObjectType.EVENT: "event"}


def severity_of(code: NeedCode, due: date | None, today: date) -> Severity:
    """*now*: race day itself, or a race day within 7 days (deadlines would be too — none
    is modelled yet); *soon*: a race day within 30 days, or undated work someone waits on;
    *info*: the rest."""
    if code in ALWAYS_NOW:
        return Severity.NOW
    if due is not None and due <= today + NOW_WITHIN:
        return Severity.NOW
    if due is not None and due <= today + SOON_WITHIN:
        return Severity.SOON
    return Severity.SOON if code in WAITED_ON else Severity.INFO


@dataclass
class Need:
    code: NeedCode
    count: int
    section: Section
    #: The date it is tied to — the race day it is for — if any.
    due: date | None = None

    @property
    def severity(self) -> Severity:
        return severity_of(self.code, self.due, date.today())

    @property
    def rank(self) -> tuple:
        """Severity, then date (undated last)."""
        return (
            SEVERITY_ORDER.index(self.severity),
            self.due is None,
            self.due or date.min,
            self.code,
        )


@dataclass
class Needs:
    """The needs of one card (*Me*, the office, a club, a series, an event), one per code."""

    kind: str
    by_code: dict[NeedCode, Need] = field(default_factory=dict)

    def add(self, code: NeedCode, count: int = 1, *, due: date | None = None) -> None:
        if count <= 0:
            return
        need = self.by_code.get(code)
        if need is None:
            self.by_code[code] = Need(code, count, SECTION_OF[(self.kind, code)], due)
            return
        need.count += count
        if due is not None and (need.due is None or due < need.due):
            need.due = due

    def get(self, code: NeedCode) -> Need | None:
        return self.by_code.get(code)

    @property
    def total(self) -> int:
        return sum(need.count for need in self.by_code.values())

    @property
    def ordered(self) -> list[Need]:
        return sorted(self.by_code.values(), key=lambda need: need.rank)


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
    relations: set[ContextRelation] = field(default_factory=set)
    needs: Needs = field(init=False)
    teams: list[TeamRef] = field(default_factory=list)
    short_name: str | None = None
    starts_on: date | None = None
    ends_on: date | None = None
    status: str | None = None
    published: bool = True
    series_id: int | None = None
    year: int | None = None

    def __post_init__(self) -> None:
        self.needs = Needs(self.kind)

    def need(self, code: NeedCode, count: int = 1, *, due: date | None = None) -> None:
        self.needs.add(code, count, due=due)

    @property
    def ordered_relations(self) -> list[ContextRelation]:
        return sorted(self.relations, key=RELATION_ORDER.index)

    @property
    def ordered_needs(self) -> list[Need]:
        return self.needs.ordered


@dataclass
class Office:
    """The league office (Story Z-10): there for anyone with a site relation — not one of
    "my" contexts, the site's reach is not a list of objects."""

    relations: list[ContextRelation]
    needs: Needs = field(default_factory=lambda: Needs("office"))


@dataclass
class TodoContext:
    """Where a to-do is: ``me`` and ``office`` have no id."""

    kind: str
    id: int | None = None


@dataclass
class Todo:
    """One row of the plan's §4: a need, and the card it sits on."""

    context: TodoContext
    need: Need


@dataclass
class MySpace:
    name: str
    needs: list[Need]
    contexts: list[Context]
    #: Everything that needs me, each thing once — what the account button's badge shows.
    total: int = 0
    office: Office | None = None
    #: Every need of every card, most urgent first.
    todos: list[Todo] = field(default_factory=list)


@dataclass
class Loaded:
    """The rows behind the contexts, for the questions asked of the model on them."""

    series: dict[int, Series] = field(default_factory=dict)
    events: dict[int, Event] = field(default_factory=dict)


ContextKey = tuple[str, int]
Contexts = dict[ContextKey, Context]


async def linked_sailor(session: AsyncSession, user: User) -> Sailor | None:
    """The sailor record under this account's **verified** address — without a 404:
    having no sailor record is a normal answer here."""
    if not user.email_verified:
        return None
    return (
        await session.execute(select(Sailor).where(Sailor.email == user.email.lower()))
    ).scalar_one_or_none()


async def require_linked_sailor(session: AsyncSession, user: User) -> Sailor:
    """:func:`linked_sailor`, for a page about *my* sailor record — the profile, my
    waivers — where having none is a 404.

    Requires the address to be **verified**: an account that merely claims an email
    proves nothing, and matching on it would let anyone view or edit any sailor's record
    just by typing their address at sign-up. The 404 is worded the same whether the
    reason is "no verified email at all" or "no sailor row uses this email" — a caller has
    no legitimate use for telling those apart.
    """
    sailor = await linked_sailor(session, user)
    if sailor is None:
        raise Problem(
            404,
            "no-linked-sailor-record",
            "No sailor record is linked to this account yet.",
            detail=(
                "An administrator or your club's leadership can create your sailor "
                "record and link it to this email address."
            ),
        )
    return sailor


async def my_space(session: AsyncSession, user: User) -> MySpace:
    contexts: Contexts = {}

    def at(kind: str, object_id: int) -> Context:
        key = (kind, object_id)
        if key not in contexts:
            contexts[key] = Context(kind=kind, id=object_id, name="")
        return contexts[key]

    site_relations: set[ContextRelation] = set()
    for relation, obj in authz.tuples(user):
        if obj.type is ObjectType.SITE and relation in ContextRelation.__members__.values():
            site_relations.add(ContextRelation(relation))
        kind = KIND_OF.get(obj.type)
        if kind is not None and obj.id is not None:
            at(kind, obj.id).relations.add(ContextRelation(relation))

    # Read once for the whole page: every waiver question below is judged against it.
    required = await current_waiver_text(session)
    sailor = await linked_sailor(session, user)
    if sailor is not None:
        await _sailing(session, sailor, at)
        await _waivers(session, sailor, required, at)

    loaded = await _fill(session, contexts)
    echoed = _series_waiver_on_events(contexts)
    _date_waivers(contexts)
    _claims(await expenses.pending(session, user), contexts)
    rejected = _rejected(await expenses.rejected_of(session, user), contexts)
    await _organizer(session, user, required, contexts)
    await _club_people(session, user, contexts)
    await _payment_runs(session, user, contexts)
    await _events(session, user, required, contexts, loaded)
    await _series(session, user, contexts, loaded)

    me = Needs("me")
    me.add(NeedCode.CLAIM_REJECTED, rejected)
    me.add(NeedCode.DOCUMENTS_EXPIRED, await _expired_documents(session, user))
    me.add(NeedCode.WARD_WAIVER, await _ward_waivers(session, user, required))

    office = None
    if site_relations:
        office = Office(relations=sorted(site_relations, key=RELATION_ORDER.index))
        if authz.check(user, Relation.ADMIN):
            await _league_office(session, office.needs)

    ordered = sorted(contexts.values(), key=_order)
    cards: list[tuple[TodoContext, Needs]] = [(TodoContext("me"), me)]
    if office is not None:
        cards.append((TodoContext("office"), office.needs))
    cards += [(TodoContext(c.kind, c.id), c.needs) for c in ordered]
    todos = [Todo(where, need) for where, needs in cards for need in needs.ordered]
    # Stable: within one rank, the order of the cards (me, office, clubs, series, events).
    todos.sort(key=lambda todo: todo.need.rank[:3])

    # Things to do, each once: a series' waiver asked again on its events is one signature.
    total = sum(needs.total for _, needs in cards) - echoed
    return MySpace(
        name=sailor.full_name if sailor is not None else user.display_name,
        needs=me.ordered,
        contexts=ordered,
        total=total,
        office=office,
        todos=todos,
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
    # A series matchday's entry holds no members: its crew is the `EventCrew` (Story V-2),
    # and being named there is what puts me in the event.
    crews = (
        await session.execute(
            select(Team.id, Team.series_id, EventCrew.event_id, Club.id, Club.name)
            .join(EventCrew, EventCrew.team_id == Team.id)
            .join(Club, Team.club_id == Club.id)
            .where(EventCrew.sailor_id == sailor.id)
            .order_by(Club.name)
        )
    ).all()
    for team_id, series_id, event_id, club_id, club_name in [*rows, *crews]:
        context = at("event", event_id) if event_id is not None else at("series", series_id)
        context.relations.add(SAILOR)
        if all(team.team_id != team_id for team in context.teams):
            context.teams.append(TeamRef(team_id, club_id, club_name))


async def _waivers(session: AsyncSession, sailor: Sailor, required: WaiverText | None, at) -> None:
    """Where the signature is given — the series, or an event in no series (S-1). The
    series' events I sail in ask for it too (`_series_waiver_on_events`)."""
    for competition, judged in await sailor_waivers(session, sailor, required):
        if judged.status not in (WaiverStatus.CLEARED, WaiverStatus.NOT_REQUIRED):
            at(competition.scope, competition.scope_id).need(NeedCode.WAIVER)


def _series_waiver_on_events(contexts: Contexts) -> int:
    """A series' waiver is signed once, on the series — but a sailor meets it on the
    matchday, so each event of the series I sail in asks for it too (Story S-1). Signing
    once clears all of them: they read the series' status, they keep none of their own."""
    unsigned = {
        object_id
        for (kind, object_id), context in contexts.items()
        if kind == "series" and context.needs.get(NeedCode.WAIVER)
    }
    echoed = 0
    for (kind, _), context in contexts.items():
        if kind == "event" and SAILOR in context.relations and context.series_id in unsigned:
            context.need(NeedCode.WAIVER)
            echoed += 1
    return echoed


def _date_waivers(contexts: Contexts) -> None:
    """A waiver is due on the race day I meet it: an event's own date, and on the series
    the next of its events I sail in (Story Z-10)."""
    today = date.today()
    for context in contexts.values():
        need = context.needs.get(NeedCode.WAIVER)
        if context.kind == "event" and need and context.starts_on and context.starts_on >= today:
            need.due = context.starts_on
            series = contexts.get(("series", context.series_id or 0))
            on_series = series.needs.get(NeedCode.WAIVER) if series else None
            if on_series and (on_series.due is None or need.due < on_series.due):
                on_series.due = need.due


async def _fill(session: AsyncSession, contexts: Contexts) -> Loaded:
    """Names and dates, one query per kind."""
    loaded = Loaded()

    def ids(kind: str) -> list[int]:
        return [object_id for (k, object_id) in contexts if k == kind]

    if club_ids := ids("club"):
        for club in (await session.execute(select(Club).where(Club.id.in_(club_ids)))).scalars():
            context = contexts[("club", club.id)]
            context.name, context.short_name = club.name, club.short_name
    if series_ids := ids("series"):
        rows = (await session.execute(select(Series).where(Series.id.in_(series_ids)))).scalars()
        for series in rows:
            loaded.series[series.id] = series
            context = contexts[("series", series.id)]
            context.name, context.short_name = series.name, series.short_name
            context.starts_on, context.ends_on = series.starts_on, series.ends_on
            context.year, context.published = series.year, series.published
    if event_ids := ids("event"):
        for event in (
            await session.execute(select(Event).where(Event.id.in_(event_ids)))
        ).scalars():
            loaded.events[event.id] = event
            context = contexts[("event", event.id)]
            context.name = event.title
            context.starts_on, context.ends_on = event.starts_on, event.ends_on
            context.status, context.published = event.status, event.published
            context.series_id = event.series_id
    # A tuple on an object that has since gone is nobody's context.
    for key in [key for key, context in contexts.items() if not context.name]:
        del contexts[key]
    return loaded


def _claims(pending: list, contexts: Contexts) -> None:
    """Each claim waiting for me, on the card I would open to deal with it: the event when
    I hold the event, else the club that pays (Story F-6)."""
    for claim in pending:
        for key in (
            ("event", claim.event_id),
            ("club", claim.payer_club_id),
            ("club", claim.club_id),
        ):
            if key[1] is not None and key in contexts:
                contexts[key].need(NeedCode.CLAIMS)
                break


def _rejected(claims: list, contexts: Contexts) -> int:
    """Each of my rejected claims, on the card of the event or club it is on — it waits on
    me now, with the decider's message (Story F-2). Returns how many have no card there,
    which the page then shows under "Me"."""
    elsewhere = 0
    for claim in claims:
        key = ("event", claim.event_id) if claim.event_id is not None else ("club", claim.club_id)
        if key in contexts:
            contexts[key].need(NeedCode.CLAIM_REJECTED)
        else:
            elsewhere += 1
    return elsewhere


def _my_clubs(user: User, relations: Relation | tuple, contexts: Contexts) -> list[int]:
    """The clubs among my contexts on which I hold one of ``relations`` (an admin
    included, as the model says)."""
    return [
        club_id
        for club_id in authz.list_objects(user, relations, ObjectType.CLUB)
        if ("club", club_id) in contexts
    ]


async def _organizer(
    session: AsyncSession,
    user: User,
    required: WaiverText | None,
    contexts: Contexts,
) -> None:
    """What only a club's organizer can fix: a running series' squad below its minimum,
    an upcoming entry with nobody named (Stories V-1, V-2)."""
    clubs = _my_clubs(user, Relation.MANAGER, contexts)
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
        contexts[("club", club_id)].need(NeedCode.SQUAD_BELOW_MIN)
    # The crew is the matchday's `EventCrew`, never the entry's `TeamMembership`: a series
    # matchday's entry holds no members at all (its squad is the series registration's),
    # and a stand-alone event's entry holds the squad — neither says who is named.
    crewed = (
        select(func.count(EventCrew.id))
        .where(EventCrew.event_id == Team.event_id, EventCrew.team_id == Team.id)
        .correlate(Team)
        .scalar_subquery()
    )
    uncrewed = (
        await session.execute(
            select(Team.club_id, Event.starts_on)
            .join(Event, Team.event_id == Event.id)
            .where(
                Team.club_id.in_(clubs),
                Team.status == TeamStatus.ACCEPTED,
                Event.status == EventStatus.PLANNED,
                Event.starts_on >= today,
                crewed == 0,
            )
        )
    ).all()
    for club_id, starts_on in uncrewed:
        contexts[("club", club_id)].need(NeedCode.CREW_MISSING, due=starts_on)

    # Story VA-5: a crew may be named before its waivers are in — the lineup stays open —
    # but the organizer is told, once per upcoming matchday with someone not cleared.
    crews = (
        await session.execute(
            select(Event, Team.club_id, EventCrew.sailor_id)
            .join(EventCrew, EventCrew.event_id == Event.id)
            .join(Team, EventCrew.team_id == Team.id)
            .where(
                Team.club_id.in_(clubs),
                Event.status == EventStatus.PLANNED,
                Event.starts_on >= today,
            )
        )
    ).all()
    by_event: dict[tuple[int, int], tuple[Event, list[int]]] = {}
    for event, club_id, sailor_id in crews:
        by_event.setdefault((event.id, club_id), (event, []))[1].append(sailor_id)
    for (_, club_id), (event, sailor_ids) in by_event.items():
        if await _not_cleared(session, event, sailor_ids, required):
            contexts[("club", club_id)].need(NeedCode.CREW_WAIVER_MISSING, due=event.starts_on)


async def _not_cleared(
    session: AsyncSession, event: Event, sailor_ids: list[int], required: WaiverText | None
) -> int:
    """How many of these sailors are not cleared to sail this event (Story VA-5)."""
    judged = await event_waiver_status(session, event, sailor_ids, required)
    return sum(
        j.status not in (WaiverStatus.CLEARED, WaiverStatus.NOT_REQUIRED) for j in judged.values()
    )


async def _club_people(session: AsyncSession, user: User, contexts: Contexts) -> None:
    """Story Z-10, for a club's organizers: its minors with no guardian linked (V-13), and
    its sailors without a date of birth, for whom no waiver can be confirmed (S-3)."""
    clubs = _my_clubs(user, Relation.MANAGER, contexts)
    if not clubs:
        return
    today = date.today()
    guarded = select(Grant.sailor_id).where(
        Grant.relation == Relation.GUARDIAN, Grant.sailor_id.is_not(None)
    )
    rows = (
        await session.execute(
            select(SailorClub.club_id, Sailor.birth_date)
            .join(Sailor, SailorClub.sailor_id == Sailor.id)
            .where(SailorClub.club_id.in_(clubs))
            .where(Sailor.birth_date.is_(None) | Sailor.id.not_in(guarded))
        )
    ).all()
    for club_id, birth_date in rows:
        if birth_date is None:
            contexts[("club", club_id)].need(NeedCode.SAILOR_WITHOUT_BIRTH_DATE)
        elif is_minor(birth_date, today):
            contexts[("club", club_id)].need(NeedCode.MINOR_WITHOUT_GUARDIAN)


async def _payment_runs(session: AsyncSession, user: User, contexts: Contexts) -> None:
    """Story Z-10: a payment run with a payment still issued — the file went to the bank,
    the statement has not booked it (F-7) — for the club's organizers and treasurer."""
    clubs = _my_clubs(user, (Relation.MANAGER, Relation.TREASURER), contexts)
    if not clubs:
        return
    rows = (
        await session.execute(
            select(PaymentRun.payer_club_id, func.count(func.distinct(PaymentRun.id)))
            .join(Payment, Payment.run_id == PaymentRun.id)
            .where(PaymentRun.payer_club_id.in_(clubs), Payment.status == PaymentStatus.ISSUED)
            .group_by(PaymentRun.payer_club_id)
        )
    ).all()
    for club_id, count in rows:
        contexts[("club", club_id)].need(NeedCode.PAYMENT_RUN_OPEN, count)


async def _events(
    session: AsyncSession,
    user: User,
    required: WaiverText | None,
    contexts: Contexts,
    loaded: Loaded,
) -> None:
    """Story Z-10, per event of mine: what its organizers and its race committee hold —
    asked of the model on the event (its series' and host club's people included)."""
    today = date.today()
    for event in loaded.events.values():
        context = contexts.get(("event", event.id))
        if context is None:
            continue
        organizer = authz.check(user, Relation.MANAGER, on=event)
        committee = organizer or authz.check(user, Relation.RACE_OFFICER, on=event)
        live = event.status == EventStatus.LIVE
        open_ = event.status in (EventStatus.PLANNED, EventStatus.LIVE)
        if organizer and event.status == EventStatus.PLANNED:
            reasons = await event_readiness(session, event)
            context.need(NeedCode.EVENT_NOT_READY, len(reasons), due=event.starts_on)
        if organizer and open_ and not event.published and event.starts_on is not None:
            context.need(NeedCode.EVENT_UNPUBLISHED, due=event.starts_on)
        if organizer:
            context.need(
                NeedCode.REGISTRATIONS_OPEN,
                await _applications(session, Team.event_id == event.id),
                due=event.starts_on,
            )
        race_week = event.starts_on is not None and event.starts_on <= today + NOW_WITHIN
        ongoing = event.ends_on is None or event.ends_on >= today
        if committee and open_ and (live or (race_week and ongoing)):
            crew = (
                await session.execute(
                    select(EventCrew.sailor_id).where(EventCrew.event_id == event.id).distinct()
                )
            ).scalars()
            context.need(
                NeedCode.CHECKIN_WAIVERS_MISSING,
                await _not_cleared(session, event, list(crew), required),
                due=event.starts_on,
            )
        if committee and live:
            missing = (
                await session.execute(
                    select(func.count(func.distinct(Race.id)))
                    .join(Flight, Race.flight_id == Flight.id)
                    .join(RaceEntry, RaceEntry.race_id == Race.id)
                    .where(
                        Flight.event_id == event.id,
                        Race.status == RaceStatus.FINISHED,
                        RaceEntry.finish_position.is_(None),
                        RaceEntry.code.is_(None),
                    )
                )
            ).scalar_one()
            context.need(NeedCode.RESULTS_MISSING, missing, due=event.starts_on)


async def _series(session: AsyncSession, user: User, contexts: Contexts, loaded: Loaded) -> None:
    """Story Z-10, per series I organize: a dated draft, and clubs' applications (V-5)
    waiting for my decision (A-9)."""
    today = date.today()
    for series in loaded.series.values():
        context = contexts.get(("series", series.id))
        if context is None or not authz.check(user, Relation.MANAGER, on=series):
            continue
        running = series.ends_on is None or series.ends_on >= today
        if not series.published and series.starts_on is not None and running:
            context.need(NeedCode.EVENT_UNPUBLISHED, due=series.starts_on)
        context.need(
            NeedCode.REGISTRATIONS_OPEN,
            await _applications(session, (Team.series_id == series.id) & Team.event_id.is_(None)),
        )


async def _applications(session: AsyncSession, where) -> int:
    """Applications still to decide (Stories V-5, A-9)."""
    return (
        await session.execute(
            select(func.count(Team.id)).where(where, Team.status == TeamStatus.REQUESTED)
        )
    ).scalar_one()


async def _league_office(session: AsyncSession, needs: Needs) -> None:
    """Story Z-10, for the site's admin: clubs enrolled in no series of a league — the
    public site does not show them — and imports whose latest run failed."""
    in_league = (
        select(Team.club_id)
        .join(Series, Team.series_id == Series.id)
        .where(Series.league_id.is_not(None), Team.status == TeamStatus.ACCEPTED)
    )
    needs.add(
        NeedCode.CLUBS_WITHOUT_LEAGUE,
        (
            await session.execute(select(func.count(Club.id)).where(Club.id.not_in(in_league)))
        ).scalar_one(),
    )
    latest: dict[tuple[str, str], bool] = {}
    runs = await session.execute(
        select(ImportRun.source, ImportRun.reference, ImportRun.ok).order_by(
            ImportRun.started_at, ImportRun.id
        )
    )
    for source, reference, ok in runs:
        latest[(source, reference)] = ok
    needs.add(NeedCode.IMPORTS_FAILED, sum(not ok for ok in latest.values()))


async def _ward_waivers(session: AsyncSession, user: User, required: WaiverText | None) -> int:
    """Story S-8: the competitions of the sailors I am guardian of whose waiver is not
    cleared yet and which I can sign — the child is a minor there (or of unknown age,
    which the club has to fix: the page says so)."""
    ward_ids = authz.list_objects(user, Relation.GUARDIAN, ObjectType.SAILOR)
    if not ward_ids:
        return 0
    count = 0
    wards = (await session.execute(select(Sailor).where(Sailor.id.in_(ward_ids)))).scalars()
    for ward in wards:
        for _, judged in await sailor_waivers(session, ward, required):
            if (
                judged.status not in (WaiverStatus.CLEARED, WaiverStatus.NOT_REQUIRED)
                and judged.minor is not False
            ):
                count += 1
    return count


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

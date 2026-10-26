"""Every paged list's search, sort and filters, declared once (Story A-13, decided
2026-10-25) — the subclasses of :class:`app.listing.ListFilter`, one per list.

A route takes its list's class as ``filters: EventFilter = ListDepends(EventFilter)``
and narrows its statement with ``filters.sort(filters.filter(stmt))``; what is the route's
own — who may see which rows, a default such as "the current year" — stays in the route.
One module, so the lists can be read side by side: a filter one list has and its sibling
lacks is visible here, not in eleven routers.

Filters are named for what they narrow to (``series_id``, ``host_club_id``, ``status``,
``published``, ``year``); the library's operators extend each where a list needs it
(``status__in``, ``starts_on__gte``).
"""

from __future__ import annotations

from datetime import date
from typing import ClassVar

from pydantic import Field, PrivateAttr
from sqlalchemy import Select, or_, select

from app.listing import ListFilter
from app.models import (
    Club,
    ClubMembership,
    Event,
    EventStatus,
    League,
    MediaItem,
    MembershipStatus,
    Person,
    Post,
    PostKind,
    Series,
    Team,
    TeamMembership,
    Venue,
)
from app.models.auth import Grant, Relation, User
from app.pagination import apply_search

#: The ``league`` filter's value for the association's own posts.
ASSOCIATION = "association"

#: The sort, asked for as ``?sort=-starts_on`` — the field is ``order_by`` (a ``sort``
#: field would hide the filter's ``sort()``), the query parameter keeps its name.
SORT = Field(
    default=None,
    alias="sort",
    description="Columns to sort by, comma-separated; '-' for descending",
)


def search_events(stmt: Select, q: str | None) -> Select:
    """Narrows an ``Event`` query to what someone searching would mean by ``q``.

    Title, venue and host club in **one** statement: the two outer joins keep it a single
    query rather than a name lookup per row, and neither can multiply an event — an event
    has at most one venue and at most one host — so ``total`` still counts events and not
    join rows. They are added only when there is something to search for, so an ordinary
    listing is the query it always was. The public calendar and the admin list share it:
    they differ in what they may show, never in what "search" means.
    """
    if not (q or "").strip():
        return stmt
    return apply_search(
        stmt.outerjoin(Venue, Event.venue_id == Venue.id).outerjoin(
            Club, Event.host_club_id == Club.id
        ),
        q,
        Event.title,
        Venue.name,
        Club.name,
        Club.short_name,
    )


def about_series(series_id: int, event_column, series_column):
    """About a series — itself or one of its events: what a series' *News & pictures*
    lists (Stories R-1, R-2)."""
    return or_(
        series_column == series_id,
        event_column.in_(select(Event.id).where(Event.series_id == series_id)),
    )


# ---------------------------------------------------------------- events


class _EventSearch(ListFilter):
    def search(self, stmt: Select, q: str | None) -> Select:
        return search_events(stmt, q)


class EventFilter(_EventSearch):
    """The admin list of events, drafts included."""

    q: str | None = Field(default=None, description="Search in title, venue and host club")
    series_id: int | None = Field(default=None, description="Only this series' events")
    host_club_id: int | None = Field(default=None, description="Only the events this club hosts")
    status: EventStatus | None = Field(default=None, description="Only events in this state")
    published: bool | None = Field(default=None, description="Only published, or only drafts")
    order_by: list[str] | None = SORT

    class Constants(ListFilter.Constants):
        model = Event
        sortable: ClassVar = {
            "title": Event.title,
            "starts_on": Event.starts_on,
            "status": Event.status,
            "matchday": Event.matchday,
        }
        # Dateless first — the one still being worked on — then newest.
        default_order: ClassVar = (Event.starts_on.desc().nulls_first(), Event.id.desc())


class PublicEventFilter(_EventSearch):
    """The public calendar — its ``year`` and ``series`` stay the route's (a default year)."""

    q: str | None = Field(default=None, description="Search in title, venue and host club")
    host_club_id: int | None = Field(default=None, description="Only the events this club hosts")
    order_by: list[str] | None = SORT

    class Constants(ListFilter.Constants):
        model = Event
        sortable: ClassVar = {
            "title": Event.title,
            "starts_on": Event.starts_on,
            "matchday": Event.matchday,
        }
        #: Undated last: SQLite puts NULL first, and an event with no date yet is the
        #: calendar's end, not its start (#47).
        default_order: ClassVar = (Event.starts_on.asc().nulls_last(), Event.id)


# ---------------------------------------------------------------- series, clubs, sailors, accounts


class SeriesFilter(ListFilter):
    q: str | None = Field(default=None, description="Search in name and short name")
    league_id: int | None = Field(default=None, description="Only this league's series")
    year: int | None = Field(default=None, description="Only this year's series")
    published: bool | None = Field(default=None, description="Only published, or only drafts")
    order_by: list[str] | None = SORT

    class Constants(ListFilter.Constants):
        model = Series
        sortable: ClassVar = {"name": Series.name, "year": Series.year, "level": Series.level}
        default_order: ClassVar = (
            Series.year.desc().nulls_last(),
            Series.level.nulls_last(),
            Series.id,
        )
        search_columns: ClassVar = (Series.name, Series.short_name)


class ClubFilter(ListFilter):
    """The admin list of clubs, and — its ``year``/``series`` being the route's — the
    public one."""

    q: str | None = Field(default=None, description="Search in name, abbreviation and city")
    order_by: list[str] | None = SORT

    class Constants(ListFilter.Constants):
        model = Club
        sortable: ClassVar = {"name": Club.name, "short_name": Club.short_name, "city": Club.city}
        default_order: ClassVar = (Club.name, Club.id)
        search_columns: ClassVar = (Club.name, Club.short_name, Club.city)


class PersonFilter(ListFilter):
    q: str | None = Field(default=None, description="Search in first name, last name, and email")
    club_id: int | None = Field(default=None, description="Only those who sail for this club")
    order_by: list[str] | None = SORT

    class Constants(ListFilter.Constants):
        model = Person
        sortable: ClassVar = {
            "last_name": Person.last_name,
            "first_name": Person.first_name,
            "email": Person.email,
            "birth_date": Person.birth_date,
        }
        default_order: ClassVar = (Person.last_name, Person.first_name, Person.id)
        search_columns: ClassVar = (Person.first_name, Person.last_name, Person.email)

    def where_club_id(self, club_id: int):
        # Being in a club is an active `ClubMembership` (Story V-4, #40), not a column.
        members = select(ClubMembership.person_id).where(
            ClubMembership.club_id == club_id, ClubMembership.status == MembershipStatus.ACTIVE
        )
        return Person.id.in_(members)


def _adult_since(today: date) -> date:
    """Born on or before this day: 18 today. 29 February counts as 28 February."""
    try:
        return today.replace(year=today.year - 18)
    except ValueError:
        return today.replace(year=today.year - 18, day=28)


class ClubPersonFilter(ListFilter):
    """*Club › People* (#45, `docs/PLAN_PEOPLE.md` §4): the club's people, each filter a
    question an organizer asks of them. The route names the club (:meth:`for_club`) and
    joins its memberships, so ``status`` is the row's."""

    q: str | None = Field(default=None, description="Search in first name, last name, and email")
    role: Relation | None = Field(
        default=None, description="Whose account holds this role on the club"
    )
    account: bool | None = Field(default=None, description="With an account to sign in, or without")
    minor: bool | None = Field(default=None, description="Under 18 today, or of age")
    no_birth_date: bool | None = Field(default=None, description="Without a date of birth")
    in_squad: bool | None = Field(
        default=None, description="In one of the club's squads this year, or in none"
    )
    status: MembershipStatus | None = Field(
        default=None, description="Active, invited or requested (Story V-15)"
    )
    order_by: list[str] | None = SORT
    _club_id: int = PrivateAttr(default=0)

    class Constants(ListFilter.Constants):
        model = Person
        sortable: ClassVar = {
            "last_name": Person.last_name,
            "first_name": Person.first_name,
            "birth_date": Person.birth_date,
        }
        default_order: ClassVar = (Person.last_name, Person.first_name, Person.id)
        search_columns: ClassVar = (Person.first_name, Person.last_name, Person.email)

    def for_club(self, club_id: int) -> ClubPersonFilter:
        self._club_id = club_id
        return self

    def where_role(self, role: Relation):
        holders = select(Grant.user_id).where(
            Grant.club_id == self._club_id, Grant.relation == role
        )
        return Person.user_id.in_(holders)

    def where_account(self, account: bool):
        return Person.user_id.is_not(None) if account else Person.user_id.is_(None)

    def where_minor(self, minor: bool):
        since = _adult_since(date.today())
        return Person.birth_date > since if minor else Person.birth_date <= since

    def where_no_birth_date(self, missing: bool):
        return Person.birth_date.is_(None) if missing else Person.birth_date.is_not(None)

    def where_in_squad(self, in_squad: bool):
        # A squad is the club's series registration (`event_id` empty), of this year.
        squads = (
            select(TeamMembership.person_id)
            .join(Team, TeamMembership.team_id == Team.id)
            .join(Series, Team.series_id == Series.id)
            .where(
                Team.club_id == self._club_id,
                Team.event_id.is_(None),
                Series.year == date.today().year,
            )
        )
        return Person.id.in_(squads) if in_squad else Person.id.not_in(squads)

    def where_status(self, status: MembershipStatus):
        return ClubMembership.status == status


class UserFilter(ListFilter):
    q: str | None = Field(default=None, description="Search in name and address")
    order_by: list[str] | None = SORT

    class Constants(ListFilter.Constants):
        model = User
        sortable: ClassVar = {"display_name": User.display_name, "email": User.email}
        default_order: ClassVar = (User.display_name, User.id)
        search_columns: ClassVar = (User.display_name, User.email)


# ---------------------------------------------------------------- editorial


class PostFilter(ListFilter):
    """Editorial's posts, drafts included."""

    q: str | None = Field(default=None, description="Search in the title")
    kind: PostKind | None = None
    league: str | None = Field(
        default=None,
        description=f"A league's slug, or ``{ASSOCIATION}`` for the association's own posts.",
    )
    published: bool | None = Field(default=None, description="Only published, or only drafts")
    event_id: int | None = Field(default=None, description="Only posts about this event")
    series_id: int | None = Field(
        default=None, description="Only posts about this series — its own and its events'"
    )
    order_by: list[str] | None = SORT

    class Constants(ListFilter.Constants):
        model = Post
        sortable: ClassVar = {"published_on": Post.published_on, "title": Post.title}
        default_order: ClassVar = (Post.published_on.desc(), Post.id.desc())
        search_columns: ClassVar = (Post.title,)

    def where_league(self, league: str):
        if league == ASSOCIATION:
            return Post.league_id.is_(None)
        return Post.league_id.in_(select(League.id).where(League.slug == league))

    def where_series_id(self, series_id: int):
        return about_series(series_id, Post.event_id, Post.series_id)


class PublicPostFilter(ListFilter):
    """The published posts — their ``kind`` and ``league`` stay the route's, which reads
    them differently (a league's page shows the association's posts too)."""

    order_by: list[str] | None = SORT

    class Constants(ListFilter.Constants):
        model = Post
        sortable: ClassVar = {"published_on": Post.published_on, "title": Post.title}
        default_order: ClassVar = (Post.published_on.desc(), Post.id.desc())


class MediaFilter(ListFilter):
    """The picture library."""

    q: str | None = Field(default=None, description="Search in name, alt text and credit")
    event_id: int | None = Field(default=None, description="An event's pictures")
    series_id: int | None = Field(
        default=None, description="A series' pictures — its own and its events'"
    )
    alt_missing: bool | None = Field(
        default=None, description="Only those whose alt text is a name"
    )
    order_by: list[str] | None = SORT

    class Constants(ListFilter.Constants):
        model = MediaItem
        sortable: ClassVar = {"created_at": MediaItem.created_at}
        default_order: ClassVar = (MediaItem.created_at.desc(), MediaItem.id.desc())
        search_columns: ClassVar = (MediaItem.original_name, MediaItem.alt, MediaItem.credit)

    def where_series_id(self, series_id: int):
        return about_series(series_id, MediaItem.event_id, MediaItem.series_id)

    def where_alt_missing(self, missing: bool):
        # `false` is "every picture", not "only the confirmed ones" — as before.
        return MediaItem.alt_confirmed.is_(False) if missing else None

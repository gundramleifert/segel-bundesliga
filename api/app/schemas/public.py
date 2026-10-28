"""Response models of the public API.

Deliberately separate schemas rather than passed-through ORM objects: the public interface
should not change just because a column is renamed. From these models, the frontend's whole
API client is generated (``scripts/gen-api-client.sh``).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.crests import crest_url
from app.models.auth import Relation
from app.models.competition import AnnouncementIssuer, EventDocumentKind, EventStatus
from app.models.org import CrewRole, InvitationState, MembershipStatus, Person
from app.models.racing import PreparatoryFlag, RaceStatus


class ClubOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    short_name: str
    city: str | None = None
    website: str | None = None
    logo_url: str | None = None
    description: str | None = None

    @model_validator(mode="after")
    def _prefer_uploaded_crest(self) -> ClubOut:
        """An uploaded crest wins over the `Club.logo_url` column — Story V-3.

        This is the load-bearing decision of the crest upload. Two sources exist for one
        idea ("the club's emblem"): a file someone uploaded, and a URL someone pasted.
        Resolving them **here, on read**, rather than by writing the file's URL into the
        column, keeps three things true:

        * `Club.logo_url` keeps its single meaning — *an externally hosted emblem*. A club
          that only has that keeps working untouched, and deleting an upload falls back to
          it instead of destroying it.
        * The file's existence stays the only state, exactly as for a sailor photo. There
          is no column that can disagree with the disk.
        * Every consumer that already reads `logo_url` — the club list, the club page, the
          admin list, and the event-logo fallback chain in `public.py::_event_out` — is
          served the uploaded crest with no change on their side and none in the frontend.

        Applies to every subclass (`ClubDetail`, `ClubAdminOut`) and to both construction
        paths, `model_validate(club)` and direct keyword construction — including the
        `ClubOut` nested in `TeamOut`, so it costs one `stat()` per serialized club. That
        is negligible next to the queries that produced the row, and it is the price of
        having exactly one source of truth instead of a column that can drift from disk.
        """
        uploaded = crest_url(self.id)
        if uploaded is not None:
            self.logo_url = uploaded
        return self


class LeagueOut(BaseModel):
    """A competition that runs year after year — the public site's top level."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    short_name: str
    name: str
    tagline: str | None = None


class LeagueSeason(BaseModel):
    """One year of a league: its series and their events, the league's page's data."""

    league: LeagueOut
    #: The year shown — the one asked for, else the league's current year.
    year: int | None
    #: Every year the league has published series in, newest first — the archive.
    years: list[int]
    series: list[SeasonSeriesOut]
    #: The events of those series in date order; an act is the events sharing a matchday.
    events: list[EventOut]
    #: Every club registered (accepted) for one of those series, once, by name.
    clubs: list[ClubOut] = []


class SeriesOut(BaseModel):
    """A Series — the name already carries the year ("DSBL 2026")."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    short_name: str
    year: int | None = None
    level: int | None = None
    #: The league this series is a year of — ``LeagueOut.id``; empty for none.
    league_id: int | None = None
    starts_on: date | None = None
    ends_on: date | None = None
    # How many people a club registers (Story V-1): the maximum is enforced, the minimum shown.
    squad_min: int = 4
    squad_max: int = 10
    # Whether the series is public. On public routes this is always true — they show
    # nothing else — but the admin views share these schemas and need to see the state.
    published: bool = False
    # Free-text, Markdown, for the public standings page. Absent unless an admin set one.
    description: str | None = None


class SeasonSeriesOut(SeriesOut):
    """A series on its league's page, with the clubs registered (accepted) for it."""

    clubs: list[ClubOut] = []


class VenueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    city: str
    water: str | None = None


class TeamOut(BaseModel):
    id: int
    name: str
    club: ClubOut
    # The club's first, second, … team in the event (Story VA-13); a page names it by the
    # club's short name and, from 2 on, this number.
    number: int = 1


class MemberOut(BaseModel):
    """A member of the seasonal squad.

    Deliberately without email and birth year: sailor names are on every results list anyway,
    contact data has no place on a public page.
    """

    id: int
    first_name: str
    last_name: str
    role: CrewRole
    # Story S-4: whether the name may link to the profile page. False renders the name as
    # plain text — it is never hidden, only the page is.
    profile_public: bool = True

    @classmethod
    def of(cls, person: Person, role: CrewRole | str) -> MemberOut:
        """A sailor as a squad or lineup names them: the name, the role, nothing personal."""
        return cls(
            id=person.id,
            first_name=person.first_name,
            last_name=person.last_name,
            role=role,
            profile_public=person.profile_public,
        )

    def announce_order(self) -> AnnounceOrder:
        """Sort key: helm, crew, substitute — the order a crew is announced — then name."""
        return AnnounceOrder(
            ROLE_ORDER.get(self.role, len(ROLE_ORDER)), self.last_name, self.first_name
        )


class AnnounceOrder(NamedTuple):
    role_rank: int
    last_name: str
    first_name: str


# Helm first, then crew, then substitute — the order a crew is announced.
ROLE_ORDER: dict[str, int] = {CrewRole.HELM: 0, CrewRole.CREW: 1, CrewRole.SUBSTITUTE: 2}


class ClubMemberOut(BaseModel):
    """A fellow member of the club, as seen by another member (Story V-10).

    Not to be confused with `MemberOut`: that one is the sporting roster (squad/lineup)
    and is public to everyone. This is the affiliation — an active ``ClubMembership``
    (#40) — and is only ever shown to the club's own people or staff. Deliberately
    without email: contact data stays the club admin's business.
    """

    person_id: int
    user_id: int | None = Field(
        default=None, description="The person's account — none for a child, for instance."
    )
    display_name: str
    status: MembershipStatus = Field(
        default=MembershipStatus.ACTIVE,
        description="Only the club's admin sees `invited` and `requested` (Story V-15).",
    )
    relations: list[Relation] = Field(
        default_factory=list, description="What this person is to the club: member, manager, …"
    )
    organizer: bool = False
    admin: bool = False


class InvitationOut(BaseModel):
    """A club's invitation to an account (Story V-16), as the club sees it."""

    club_id: int
    person_id: int
    expires_at: datetime
    state: InvitationState


class ClubPersonOut(BaseModel):
    """One row of *Club › People* (#45). For a plain member the row is the roster's —
    name, account and roles; the address and the date of birth are the organizers'
    (Story V-10), left empty for everyone else."""

    person_id: int
    user_id: int | None = None
    first_name: str
    last_name: str
    status: MembershipStatus | None = Field(
        default=None, description="Empty for an organizer who is no member"
    )
    roles: list[Relation] = Field(
        default_factory=list, description="What their account is to the club besides"
    )
    email: str | None = None
    account_email: str | None = Field(
        default=None,
        description="The account's address, which roles are written to — the organizers'",
    )
    birth_date: date | None = None
    minor: bool | None = Field(default=None, description="Empty without a date of birth")
    in_squad: bool = Field(default=False, description="In one of the club's squads this year")
    invitation: InvitationOut | None = Field(
        default=None, description="The club's open invitation to an account — the organizers'"
    )


class InvitationIn(BaseModel):
    """Whom the club's admin invites: an address no account has, and the name the club
    knows them by."""

    email: EmailStr
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)


class ClubMemberIn(BaseModel):
    """Who the club's admin adds (Story Z-5): a person, by their address or their
    account's."""

    email: str = Field(min_length=3, max_length=254)


class ClubCrewOut(BaseModel):
    """One of the club's teams in an event and who sails in it (Story VA-13)."""

    team_id: int
    team_name: str
    members: list[MemberOut] = Field(default_factory=list)


class ClubEventOut(BaseModel):
    """A matchday from the club's perspective — with those who sail there for it.

    One crew per team the club entered: ``KiYC 1`` and ``KiYC 2`` sail as two crews and
    are named as two, never merged into one list.
    """

    event: EventOut
    crews: list[ClubCrewOut] = Field(default_factory=list)


class ClubTeamOut(BaseModel):
    """The club's entry in a series: the seasonal squad and the matchdays."""

    id: int
    name: str
    series: SeriesOut
    members: list[MemberOut] = Field(default_factory=list)
    events: list[ClubEventOut] = Field(default_factory=list)


class ClubDetail(ClubOut):
    """The club page.

    Matchdays of a series stand below their team — that's where they belong, along with
    squad and lineup. Events without a series have no place in this nesting and stand separately.
    """

    teams: list[ClubTeamOut] = Field(default_factory=list)
    events: list[ClubEventOut] = Field(default_factory=list)


class EventOut(BaseModel):
    id: int
    slug: str
    title: str
    # Only set for series matchdays; a standalone event stands on its own.
    matchday: int | None = None
    # Absent while the date is still being negotiated — an event is savable incomplete
    # (Story VA-8). It cannot be started without one.
    starts_on: date | None = None
    ends_on: date | None = None
    status: EventStatus
    # Public visibility, orthogonal to `status`. Always true on public routes.
    published: bool = False
    series: SeriesOut | None = None
    # Often only the date and host club are set when creating.
    venue: VenueOut | None = None
    host_club: ClubOut | None = None
    # Event's own logo, otherwise the host club's crest.
    logo_url: str | None = None
    # An external live view; None means the internal map is the live view (Story L-1).
    live_url: str | None = None
    team_count: int
    boat_count: int
    flight_count: int
    # How many teams one club may enter (Story VA-13).
    teams_per_club: int = 1
    # ceil(team_count / boat_count): the races of one flight, so every team sails once.
    races_per_flight: int = 0
    crew_size: int
    # The squad's size when the event stands alone (Story V-1); a series event uses its
    # series' limits.
    squad_min: int = 4
    squad_max: int = 10
    # How the pairing list is printed (Story B-3). Empty is the normal case and means the
    # defaults the configuration implies; the organizer's screen shows what is set here.
    print_settings: dict[str, Any] | None = None


class EventStandingRow(BaseModel):
    """A row of the event standings."""

    rank: int
    team: TeamOut
    total: float
    net: float
    races_scored: int
    # Points per race, key is the sequential race number (1..48).
    points_by_race: dict[int, float]
    # The same points summed per flight (key: flight number), only for flights this team
    # has a result in — computed from each race's own flight (Story B-2).
    points_by_flight: dict[int, float] = {}
    discarded_races: list[int]
    # The matchday penalty, already inside ``total`` and ``net`` (Story WL-4) — shown so a
    # total that is not the sum of its races explains itself.
    penalty_points: float = 0.0
    penalty_note: str | None = None


class EventDetail(BaseModel):
    event: EventOut
    standings: list[EventStandingRow]
    races_total: int
    races_scored: int


class EventAccess(BaseModel):
    """What the person asking may do on one event — Story WL-3.

    Answered per event with the permission model (``app/authz.py``), so a race officer of
    one event sees the committee's tools there and nowhere else, and one appointed through
    the series or the host club sees them too. A guest gets ``false`` throughout. The
    summary roles (``User.roles``) are for navigation and never answer this.
    """

    #: The race committee's tools: results, race control, the course, trackers
    #: (``race_officer`` on the event — directly or through its series, host club, site).
    record_results: bool = False
    #: Start, finish, cancel and reopen the day (``manager`` or ``race_officer``).
    control: bool = False
    #: The organizer's setup screen (``manager`` on the event).
    manage: bool = False
    #: Whom this person may publish announcements as on the notice board (Story VA-11) —
    #: each issuer is a relation on the event. Empty: no form.
    announce_as: list[AnnouncementIssuer] = Field(default_factory=list)


class TeamCrewOut(BaseModel):
    """One team entered in an event, and who sails it there.

    Deliberately the same `MemberOut` as the squad and the club page: a lineup and a squad
    are the same kind of public fact — id, name, role, and nothing about the person.
    """

    team: TeamOut
    #: Helm first, then crew, then substitute — the order a crew is announced. Empty while
    #: nobody is named yet, which is an answer, not a missing row.
    crew: list[MemberOut] = Field(default_factory=list)


class EventCrewList(BaseModel):
    """Who sails for every team at one matchday — Story B-12."""

    event: EventOut
    teams: list[TeamCrewOut] = Field(default_factory=list)


class SeriesStandingRow(BaseModel):
    """A row of the series standings."""

    rank: int
    team: TeamOut
    points: float
    # Ranking per matchday, key is the matchday number.
    ranks_by_matchday: dict[int, int]
    # Matchdays where the team did not participate — there the team received participant count + 1.
    missed_matchdays: list[int] = Field(default_factory=list)
    events_sailed: int = 0


class LiveNowOut(BaseModel):
    """Where ``/live`` should lead right now (Story B-5).

    The running event if there is one, otherwise the next published date — so the page
    never opens on an empty table. ``event`` is ``None`` only when nothing at all lies
    ahead.
    """

    event: EventOut | None
    #: True when ``event`` is being sailed right now, false when it is the next date.
    running: bool


class SeriesTable(BaseModel):
    """The series standings including its matchdays."""

    series: SeriesOut
    rows: list[SeriesStandingRow]
    events: list[EventOut]


class StartSequence(BaseModel):
    """The start sequence as the race committee's screen holds it — Stories WL-3, B-5.

    Times are milliseconds since the epoch on the committee phone's clock, because that is
    what the screen computes with; the live page derives flags, next signal and countdown
    from them with the same code (`web/src/lib/startSequence.ts`).
    """

    preparatory: PreparatoryFlag
    first_signal_at: int | None = Field(
        default=None,
        description="When the club flag goes up (3 minutes to go), ms since the epoch; "
        "null while no sequence is armed",
    )
    lowering: Literal["AP", "firstSubstitute"] | None = Field(
        default=None,
        description="The flag lowered one minute before the club flag goes up, if any",
    )
    ap_up_at: int | None = Field(
        default=None, description="AP was tapped during the sequence and goes up then"
    )
    first_substitute: bool = Field(
        default=False, description="A general recall left the First Substitute up"
    )


class BoatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    number: int
    # On the water, boats are referred to by color and name, not by number.
    color: str | None = None
    name: str | None = None
    sail_number: str | None = None


class EventDocumentOut(BaseModel):
    """A document on an event's notice board — a link to where it was published
    (Story A-14)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    kind: EventDocumentKind
    url: str
    extension: str | None = None
    published_at: datetime | None = None


class AnnouncementOut(BaseModel):
    """A notice on an event's notice board, from its race committee, jury or organizer
    (Story VA-11) — numbered, and signed with the publisher's name, as a notice on the
    board is."""

    id: int
    event_id: int
    #: "Notice 3" — per event, in the order published.
    number: int
    issuer: AnnouncementIssuer
    title: str
    body: str = ""
    #: When it went up.
    created_at: datetime
    #: The publisher's display name; empty once the account is gone.
    author: str | None = None

    @field_validator("created_at")
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        # Written in UTC, but SQLite stores no zone and hands it back naive — serialized
        # without one, a browser reads it as local time and the board is hours off.
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class PairingRow(BaseModel):
    """A race in the pairing list: which team on which boat."""

    sequence: int
    flight: int
    race_in_flight: int
    status: RaceStatus
    # Boat number -> Team
    teams_by_boat: dict[int, TeamOut]


class PairingList(BaseModel):
    event: EventOut
    boats: list[BoatOut]
    races: list[PairingRow]
    # Whether this installation can render the printable sheet at all — the renderer is a
    # Java tool that a deployment may not carry (Story B-3). The screen asks so it can
    # leave the download out instead of offering a button whose only answer is 503.
    pdf_available: bool = False


class PersonTeamOut(BaseModel):
    """Which club and which series a person is registered for in a season."""

    team_id: int
    role: CrewRole
    club: ClubOut
    series: SeriesOut


class PersonEventOut(BaseModel):
    """A matchday for which the person is lined up."""

    event: EventOut
    team_id: int
    role: CrewRole


class PersonDetail(BaseModel):
    """The sailor page: who the person is, who they register for, where they sail."""

    id: int
    first_name: str
    last_name: str
    # Story S-4: false when only a connected viewer (the sailor, admin/editor, their club's
    # manager) gets to see this page — the page says so to them.
    profile_public: bool = True
    teams: list[PersonTeamOut] = Field(default_factory=list)
    events: list[PersonEventOut] = Field(default_factory=list)


class MySeriesOut(BaseModel):
    """A series, as it appears on a club's own registration row."""

    id: int
    slug: str
    name: str
    year: int | None = None


class MyTeamOut(BaseModel):
    """One series registration of a club — what a squad hangs off (Story V-1)."""

    team_id: int
    series: MySeriesOut
    #: How many people are registered. On the row so a screen listing several
    #: registrations can show "7 of 4–10" without opening each squad in turn.
    squad_size: int
    squad_min: int = 4
    squad_max: int = 10


class MyEventOut(BaseModel):
    """One event entry of a club — what a lineup is set on (Stories V-2, V-12).

    Two team ids on purpose: ``team_id`` is the entry to *this* event, where the crew is
    recorded; ``squad_team_id`` is where the crew is drawn from — the series registration
    for a matchday of a series, the entry itself for an event that stands alone.
    """

    event_id: int
    slug: str
    title: str
    starts_on: date | None = None
    ends_on: date | None = None
    status: EventStatus
    #: A draft is listed for its own participants — they line up before it goes public.
    published: bool
    matchday: int | None = None
    crew_size: int
    series: MySeriesOut | None = None
    team_id: int
    squad_team_id: int
    # The club's first, second, … team in this event, and its name (Story VA-13): a club
    # with two teams there has two rows, each lined up on its own.
    number: int = 1
    team_name: str = ""


class MyClubOut(BaseModel):
    """A club this account has something to do with — Stories B-10 and V-12.

    The two relationships are kept apart because they are genuinely different and the two
    screens reading this need different ones: `/clubs` lists what someone *belongs to*,
    `/club` opens what they may *act for*. A club's organizer is frequently not in the
    sailing squad and need not be an accepted member at all, and almost every member
    manages nothing.
    """

    club: ClubOut
    #: Holds `member` on the club (Story Z-5).
    is_member: bool
    #: `team_manager` for this club — granted per club, never globally.
    may_manage: bool
    may_admin: bool = False
    teams: list[MyTeamOut]
    #: The club's event entries, next matchday first (Story V-12).
    events: list[MyEventOut] = Field(default_factory=list)

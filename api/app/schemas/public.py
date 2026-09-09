"""Response models of the public API.

Deliberately separate schemas rather than passed-through ORM objects: the public interface
should not change just because a column is renamed. From these models, the TypeScript types
of the frontend are generated via ``openapi-typescript``.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.crests import crest_url


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


class SeriesOut(BaseModel):
    """A Series — the name already carries the year ("DSBL 2026")."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    short_name: str
    year: int | None = None
    level: int | None = None
    starts_on: date | None = None
    ends_on: date | None = None
    # Free-text, Markdown, for the public standings page. Absent unless an admin set one.
    description: str | None = None


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


class MemberOut(BaseModel):
    """A member of the seasonal squad.

    Deliberately without email and birth year: sailor names are on every results list anyway,
    contact data has no place on a public page.
    """

    id: int
    first_name: str
    last_name: str
    role: str


class ClubMemberOut(BaseModel):
    """A fellow member of the club, as seen by another active member.

    Not to be confused with `MemberOut`: that one is the sporting roster (squad/lineup)
    and is public to everyone. This describes `ClubMember` — the account's affiliation
    with the club — and is only ever shown to that club's own active members or staff.
    Deliberately without email or decision notes, and only active memberships: contact
    data and pending requests stay the club leadership's business (see `MembershipOut`
    in `app.routers.club_members`), not something every peer should see.
    """

    user_id: int
    display_name: str
    # Whether this member also organizes the club (holds `club_manager` for it) — same
    # logic as `MembershipOut.organizer`.
    organizer: bool = False


class ClubEventOut(BaseModel):
    """A matchday from the club's perspective — with those who sail there for it."""

    event: EventOut
    crew: list[MemberOut] = Field(default_factory=list)


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
    starts_on: date
    ends_on: date
    status: str
    series: SeriesOut | None = None
    # Often only the date and host club are set when creating.
    venue: VenueOut | None = None
    host_club: ClubOut | None = None
    # Event's own logo, otherwise the host club's crest.
    logo_url: str | None = None
    team_count: int
    boat_count: int
    flight_count: int
    crew_size: int


class EventStandingRow(BaseModel):
    """A row of the event standings."""

    rank: int
    team: TeamOut
    total: float
    net: float
    races_scored: int
    # Points per race, key is the sequential race number (1..48).
    points_by_race: dict[int, float]
    discarded_races: list[int]


class EventDetail(BaseModel):
    event: EventOut
    standings: list[EventStandingRow]
    races_total: int
    races_scored: int


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


class SeriesTable(BaseModel):
    """The series standings including its matchdays."""

    series: SeriesOut
    rows: list[SeriesStandingRow]
    events: list[EventOut]


class BoatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    number: int
    # On the water, boats are referred to by color and name, not by number.
    color: str | None = None
    name: str | None = None
    sail_number: str | None = None


class PairingRow(BaseModel):
    """A race in the pairing list: which team on which boat."""

    sequence: int
    flight: int
    race_in_flight: int
    status: str
    # Boat number -> Team
    teams_by_boat: dict[int, TeamOut]


class PairingList(BaseModel):
    event: EventOut
    boats: list[BoatOut]
    races: list[PairingRow]


class SailorTeamOut(BaseModel):
    """Which club and which series a person is registered for in a season."""

    team_id: int
    role: str
    club: ClubOut
    series: SeriesOut


class SailorEventOut(BaseModel):
    """A matchday for which the person is lined up."""

    event: EventOut
    team_id: int
    role: str


class SailorDetail(BaseModel):
    """The sailor page: who the person is, who they register for, where they sail."""

    id: int
    first_name: str
    last_name: str
    teams: list[SailorTeamOut] = Field(default_factory=list)
    events: list[SailorEventOut] = Field(default_factory=list)

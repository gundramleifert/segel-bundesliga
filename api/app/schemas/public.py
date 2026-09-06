"""Response models of the public API.

Deliberately separate schemas rather than passed-through ORM objects: the public interface
should not change just because a column is renamed. From these models, the TypeScript types
of the frontend are generated via ``openapi-typescript``.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


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

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.competition import Event, Series
    from app.models.racing import RaceEntry


class TeamStatus(StrEnum):
    """How a participation came about, and where it stands.

    A club can apply on its own (Story V-5) — then the participation is ``requested`` and
    doesn't count anywhere yet. Only acceptance by the admin (A-9) turns it into an actual
    participation. When the admin assigns it directly (A-3, A-6), it's ``accepted``
    immediately.
    """

    REQUESTED = "requested"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class CrewRole(StrEnum):
    HELM = "helm"
    CREW = "crew"
    SUBSTITUTE = "substitute"


class Club(Base, TimestampMixin):
    __tablename__ = "club"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    short_name: Mapped[str] = mapped_column(String(32))
    # The name is enough to create it; the rest comes later.
    city: Mapped[str | None] = mapped_column(String(120), default=None)
    website: Mapped[str | None] = mapped_column(String(300), default=None)
    logo_url: Mapped[str | None] = mapped_column(String(300), default=None)
    # A few sentences for the club page — no rich text, no formatting.
    description: Mapped[str | None] = mapped_column(String(2000), default=None)
    lat: Mapped[float | None] = mapped_column(Numeric(9, 6), default=None)
    lon: Mapped[float | None] = mapped_column(Numeric(9, 6), default=None)
    # The rates this club reimburses for the events it hosts — km rate, per-diem, which
    # costs need a document, who may claim (Stories F-2, F-5). JSON like
    # ``Series.scoring``: rates differ between clubs and change between years, and nothing
    # queries them. Empty is the normal case and means the site's default.
    expense_policy: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)

    teams: Mapped[list[Team]] = relationship(back_populates="club")


class Sailor(Base, TimestampMixin):
    __tablename__ = "sailor"

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80))
    # The link to the account: this address is how the person signs in and submits their
    # liability waiver (Stories V-1 and S-1). Nullable, because people imported from
    # external systems don't always come with one.
    email: Mapped[str | None] = mapped_column(String(254), unique=True, index=True, default=None)
    birth_date: Mapped[date | None] = mapped_column(Date, default=None)
    # DSV sailing number or similar — personal data, see the deletion policy.
    federation_id: Mapped[str | None] = mapped_column(String(40), default=None, index=True)
    # Story S-4: the sailor's own choice whether their profile page is public. Empty means
    # "never chosen" — then the default follows age (`profile_public`), so a minor's page
    # starts hidden and opens by itself on the eighteenth birthday unless they decided.
    # Only the sailor's own account writes this (`PATCH /api/sailors/me`).
    profile_public_choice: Mapped[bool | None] = mapped_column(default=None)

    memberships: Mapped[list[TeamMembership]] = relationship(back_populates="sailor")
    # The clubs this person sails for — the ``club`` edge of a sailor in the permission
    # model (``manager from club``, `app/models/auth.py`). Loaded with the sailor, as an
    # event brings its host club: every check on a sailor walks it.
    club_links: Mapped[list[SailorClub]] = relationship(
        back_populates="sailor", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def club_ids(self) -> list[int]:
        return sorted(link.club_id for link in self.club_links)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def profile_public(self) -> bool:
        """Whether the profile page is public (Story S-4): the sailor's choice, else by age.

        No birth date counts as an adult here — guessing "minor" would hide most people
        on record, and the switch is the sailor's to turn off either way.
        """
        if self.profile_public_choice is not None:
            return self.profile_public_choice
        from app.services.waivers import is_minor  # the services import the models

        return is_minor(self.birth_date, date.today()) is not True


class Team(Base, TimestampMixin):
    """A club's participation — for a series, in an event, or both.

    Two levels in the same table, told apart by ``event_id``:

    * **Series registration** (``event_id`` empty). The squad (``TeamMembership``) hangs
      off this, and it decides whether the club appears publicly. Because the series
      carries its year, a registration for "DSBL 2026" doesn't carry over to "DSBL 2027".
    * **Entry in an event** (``event_id`` set). The pairing list hangs off the event —
      and so do the teams that appear in it. Results (``RaceEntry``), lineup
      (``EventCrew``) and the daily standings point to this row.

    If the event belongs to a series, the row carries **both** ids: whoever enters an act
    is also registered for its series. A standalone event has no series — then
    ``series_id`` stays empty. Both may never be empty at once.

    A club can be registered for the series without entering every act; it then gets
    field size + 1 there (``app/services/standings.py``). The reverse isn't possible.

    ``status`` distinguishes the two ways to participate: the admin assigns it directly,
    or the club applies and gets accepted. Both end up as the same row.
    """

    __tablename__ = "team"
    __table_args__ = (
        # A club's team enters an event at most once — its first, second, … team are
        # different rows (Story VA-13). Rows without an event don't interfere here: NULL is
        # never considered equal to itself in SQL.
        UniqueConstraint("club_id", "event_id", "number"),
        # The same statement for the series registration — as a partial index, because an
        # ordinary unique constraint on (club_id, series_id) would also count the act rows.
        Index(
            "uq_team_series_registration",
            "club_id",
            "series_id",
            unique=True,
            sqlite_where=text("event_id IS NULL"),
            postgresql_where=text("event_id IS NULL"),
        ),
        CheckConstraint(
            "series_id IS NOT NULL OR event_id IS NOT NULL",
            name="team_has_a_competition",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    club_id: Mapped[int] = mapped_column(ForeignKey("club.id"), index=True)
    # The club's first, second, … team in an event (Story VA-13) — 1 unless the event lets
    # a club enter more than one. A series registration is always 1: the club has one
    # squad, and every team it enters is lined up from it.
    number: Mapped[int] = mapped_column(default=1, server_default="1")
    # Empty only for a standalone event that belongs to no series.
    series_id: Mapped[int | None] = mapped_column(ForeignKey("series.id"), index=True, default=None)
    # Empty for a series registration; set for an entry in an event.
    event_id: Mapped[int | None] = mapped_column(ForeignKey("event.id"), index=True, default=None)

    # Only an accepted participation counts: public, in the standings, for lineups.
    # A requested one is visible to the club and the admin, nowhere else.
    status: Mapped[str] = mapped_column(String(16), default=TeamStatus.ACCEPTED, index=True)
    # For a rejection: why. The club should find out.
    decision_note: Mapped[str | None] = mapped_column(String(500), default=None)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    # Penalty points for the matchday as a whole (Story WL-4) — SAP's "carried points":
    # added once to the team's total and net, before its first race, and never discarded.
    # Only on an entry in an event; raw data like a finish position, set by the race
    # committee or the jury, and the points stay derived from it.
    penalty_points: Mapped[float | None] = mapped_column(default=None)
    penalty_note: Mapped[str | None] = mapped_column(String(300), default=None)

    club: Mapped[Club] = relationship(back_populates="teams")
    series: Mapped[Series | None] = relationship(back_populates="teams")
    event: Mapped[Event | None] = relationship(back_populates="teams")
    memberships: Mapped[list[TeamMembership]] = relationship(
        back_populates="team", cascade="all, delete-orphan"
    )
    race_entries: Mapped[list[RaceEntry]] = relationship(back_populates="team")

    @property
    def is_series_registration(self) -> bool:
        """The registration for the whole series — not the entry in a single act."""
        return self.event_id is None


class SailorClub(Base, TimestampMixin):
    """A sailor sails for this club (Story V-4) — the tuple ``club:3 club sailor:7`` an
    FGA server would hold, kept as a row because its subject is a club, not a user.

    It is what makes a person a club's to put in a squad, to change, to sign a waiver for
    and to link a parent to: a club's organizer connects the people they create, and only
    a club the person already sails for connects them to another (decided 2026-10-25 —
    before, putting someone in a squad was enough, so any club could take anyone).
    """

    __tablename__ = "sailor_club"
    __table_args__ = (UniqueConstraint("sailor_id", "club_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sailor_id: Mapped[int] = mapped_column(ForeignKey("sailor.id", ondelete="CASCADE"), index=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("club.id", ondelete="CASCADE"), index=True)

    sailor: Mapped[Sailor] = relationship(back_populates="club_links")


class TeamMembership(Base, TimestampMixin):
    __tablename__ = "team_membership"
    # A person is on a squad once — the router says so politely
    # (`squad-duplicate-sailor`), this makes it true for every other writer too.
    __table_args__ = (UniqueConstraint("team_id", "sailor_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), index=True)
    sailor_id: Mapped[int] = mapped_column(ForeignKey("sailor.id"), index=True)
    role: Mapped[str] = mapped_column(String(16), default=CrewRole.CREW)
    valid_from: Mapped[date | None] = mapped_column(Date, default=None)
    valid_to: Mapped[date | None] = mapped_column(Date, default=None)

    team: Mapped[Team] = relationship(back_populates="memberships")
    sailor: Mapped[Sailor] = relationship(back_populates="memberships")

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
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
    from app.models.auth import User
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


class ClubMemberStatus(StrEnum):
    """Where a club membership stands — and whose turn it is to act next.

    Both directions need the other side's consent: nobody becomes a member of a club
    unasked, and no club gets members unasked. The status therefore says not just "open",
    but **who** still needs to agree.
    """

    PENDING_CLUB = "pending_club"
    """The person has asked — the club needs to accept."""

    PENDING_USER = "pending_user"
    """The club has invited — the person needs to accept."""

    ACTIVE = "active"
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

    memberships: Mapped[list[TeamMembership]] = relationship(back_populates="sailor")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


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
        # A club enters an event at most once. Rows without an event don't interfere here:
        # NULL is never considered equal to itself in SQL.
        UniqueConstraint("club_id", "event_id"),
        # The same statement for the series registration — as a partial index, because an
        # ordinary unique constraint on (club_id, series_id) would also count the act rows.
        Index(
            "uq_team_series_meldung",
            "club_id",
            "series_id",
            unique=True,
            sqlite_where=text("event_id IS NULL"),
            postgresql_where=text("event_id IS NULL"),
        ),
        CheckConstraint(
            "series_id IS NOT NULL OR event_id IS NOT NULL",
            name="team_hat_einen_wettbewerb",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    club_id: Mapped[int] = mapped_column(ForeignKey("club.id"), index=True)
    # Empty only for a standalone event that belongs to no series.
    series_id: Mapped[int | None] = mapped_column(
        ForeignKey("series.id"), index=True, default=None
    )
    # Empty for a series registration; set for an entry in an event.
    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("event.id"), index=True, default=None
    )

    # Only an accepted participation counts: public, in the standings, for lineups.
    # A requested one is visible to the club and the admin, nowhere else.
    status: Mapped[str] = mapped_column(String(16), default=TeamStatus.ACCEPTED, index=True)
    # For a rejection: why. The club should find out.
    decision_note: Mapped[str | None] = mapped_column(String(500), default=None)
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    club: Mapped[Club] = relationship(back_populates="teams")
    series: Mapped[Series | None] = relationship(back_populates="teams")
    event: Mapped[Event | None] = relationship(back_populates="teams")
    memberships: Mapped[list[TeamMembership]] = relationship(
        back_populates="team", cascade="all, delete-orphan"
    )
    race_entries: Mapped[list[RaceEntry]] = relationship(back_populates="team")

    @property
    def ist_serienmeldung(self) -> bool:
        """The registration for the whole series — not the entry in a single act."""
        return self.event_id is None


class TeamMembership(Base, TimestampMixin):
    __tablename__ = "team_membership"

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), index=True)
    sailor_id: Mapped[int] = mapped_column(ForeignKey("sailor.id"), index=True)
    role: Mapped[str] = mapped_column(String(16), default=CrewRole.CREW)
    valid_from: Mapped[date | None] = mapped_column(Date, default=None)
    valid_to: Mapped[date | None] = mapped_column(Date, default=None)

    team: Mapped[Team] = relationship(back_populates="memberships")
    sailor: Mapped[Sailor] = relationship(back_populates="memberships")


class ClubMember(Base, TimestampMixin):
    """Who belongs to which club — and whether both sides have agreed.

    A person can be in multiple clubs (Story V-7); the "only once per competition"
    restriction only kicks in for series and events, not here.

    A membership comes about in one of two ways, and **both need the other side's
    consent**:

    * The person asks (``PENDING_CLUB``) — the club's leadership accepts.
    * The club invites (``PENDING_USER``) — the person accepts.

    That's what sets membership apart from participation in a series or event
    (``Team``): there, the admin also assigns it **unilaterally**, because it runs the
    competition. The reverse direction there needs the admin's approval.
    """

    __tablename__ = "club_member"
    __table_args__ = (UniqueConstraint("club_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("club.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), index=True)
    # For a rejection: why. The rejected side should find out.
    decision_note: Mapped[str | None] = mapped_column(String(500), default=None)
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    club: Mapped[Club] = relationship()
    user: Mapped[User] = relationship()

    @property
    def wartet_auf_verein(self) -> bool:
        return self.status == ClubMemberStatus.PENDING_CLUB

    @property
    def wartet_auf_person(self) -> bool:
        return self.status == ClubMemberStatus.PENDING_USER

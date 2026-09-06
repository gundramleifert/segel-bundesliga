from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.competition import Event
    from app.models.org import Team


class ResultCode(StrEnum):
    """Scoring codes per RRS Appendix A."""

    FINISHED = "FINISHED"
    DNS = "DNS"  # did not start
    DNF = "DNF"  # did not finish
    OCS = "OCS"  # on course side (early start)
    DSQ = "DSQ"  # disqualified
    DNE = "DNE"  # disqualification not excludable
    RDG = "RDG"  # redress
    ZFP = "ZFP"  # 20% penalty
    SCP = "SCP"  # scoring penalty
    RET = "RET"  # retired


# Order as in the pairing lists: boat 1 is black, boat 6 is orange.
BOAT_COLORS = ("BLACK", "GREEN", "DARKBLUE", "RED", "GRAY", "ORANGE")


class RaceStatus(StrEnum):
    SCHEDULED = "scheduled"
    RUNNING = "running"
    FINISHED = "finished"
    ABANDONED = "abandoned"


class Boat(Base, TimestampMixin):
    """One of the six identical league boats of a matchday.

    The pairing lists list them as BLACK, GREEN, DARKBLUE, RED, GRAY, ORANGE.
    """

    __tablename__ = "boat"
    __table_args__ = (UniqueConstraint("event_id", "number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("event.id"), index=True)
    number: Mapped[int]
    color: Mapped[str | None] = mapped_column(String(24), default=None)
    sail_number: Mapped[str | None] = mapped_column(String(32), default=None)
    name: Mapped[str | None] = mapped_column(String(80), default=None)

    event: Mapped[Event] = relationship(back_populates="boats")
    race_entries: Mapped[list[RaceEntry]] = relationship(back_populates="boat")


class Flight(Base, TimestampMixin):
    """A round: three races, after which each of the 18 teams has sailed once."""

    __tablename__ = "flight"
    __table_args__ = (UniqueConstraint("event_id", "number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("event.id"), index=True)
    number: Mapped[int]

    event: Mapped[Event] = relationship(back_populates="flights")
    races: Mapped[list[Race]] = relationship(
        back_populates="flight", cascade="all, delete-orphan", order_by="Race.number_in_flight"
    )


class Race(Base, TimestampMixin):
    __tablename__ = "race"
    __table_args__ = (UniqueConstraint("flight_id", "number_in_flight"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    flight_id: Mapped[int] = mapped_column(ForeignKey("flight.id"), index=True)
    number_in_flight: Mapped[int]
    # Sequential across the whole matchday (1..48) — the number that appears on result
    # sheets.
    sequence: Mapped[int] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(String(16), default=RaceStatus.SCHEDULED)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    # Optimistic lock for the race committee's offline sync.
    version: Mapped[int] = mapped_column(default=0)

    flight: Mapped[Flight] = relationship(back_populates="races")
    entries: Mapped[list[RaceEntry]] = relationship(
        back_populates="race", cascade="all, delete-orphan"
    )


class EventCrew(Base, TimestampMixin):
    """Who sails for a team at **this** matchday.

    Two levels that mustn't be confused:

    * ``TeamMembership`` is the **season squad** — who's allowed to enter for the club in
      this league at all (ten people, Story V-1).
    * ``EventCrew`` is the **lineup for a matchday** — who actually sails (four people,
      Story V-2).

    A person sails for at most one team at a given matchday; otherwise they'd be on two
    boats at once.
    """

    __tablename__ = "event_crew"
    __table_args__ = (UniqueConstraint("event_id", "sailor_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("event.id"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), index=True)
    sailor_id: Mapped[int] = mapped_column(ForeignKey("sailor.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))


class RaceEntry(Base, TimestampMixin):
    """Team on a boat in a race — both a pairing-list row and the result holder.

    The pairing list exists before the race (``code`` is NULL then), and the result fills
    in the same row. Deliberately no separate ``Result`` table: one join fewer, and the
    one-to-one relationship would be enforced anyway.

    Authoritative are the raw fields ``code``, ``finish_position`` and
    ``redress_points``. The points next to them are derived and rewritten on every
    change — never set by hand. That way a protest decision stays a data change and never
    becomes a data migration.
    """

    __tablename__ = "race_entry"
    __table_args__ = (
        UniqueConstraint("race_id", "team_id"),
        UniqueConstraint("race_id", "boat_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("race.id"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), index=True)
    boat_id: Mapped[int] = mapped_column(ForeignKey("boat.id"), index=True)

    code: Mapped[str | None] = mapped_column(String(16), default=None)
    finish_position: Mapped[int | None] = mapped_column(default=None)
    # Only set for RDG: the score awarded by the jury.
    redress_points: Mapped[float | None] = mapped_column(default=None)

    # The scored points. Derived: recalculated from the raw data above on every result
    # change (app/services/standings.py). Stored so queries, exports and rankings can
    # read it directly — never to be set by hand. A protest decision changes `code` or
    # `finish_position`, after which it's recalculated.
    points: Mapped[float | None] = mapped_column(default=None)
    is_discarded: Mapped[bool] = mapped_column(default=False)

    race: Mapped[Race] = relationship(back_populates="entries")
    team: Mapped[Team] = relationship(back_populates="race_entries")
    boat: Mapped[Boat] = relationship(back_populates="race_entries")

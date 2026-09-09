from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, Date, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.org import Club, Team
    from app.models.racing import Boat, Flight


class EventStatus(StrEnum):
    """Where an event stands **sportingly** — deliberately not whether it is public.

    ``planned`` → ``live`` → ``final``, with ``cancelled`` as the way out. Publication is
    a separate flag (``published``): the two are orthogonal, so a published event can still
    be ``planned``, and a draft can be worked on for weeks without anyone seeing it. See
    ``app/services/event_readiness.py`` for what has to be true before an event may go
    ``live``.
    """

    PLANNED = "planned"
    LIVE = "live"
    FINAL = "final"
    CANCELLED = "cancelled"


class Series(Base, TimestampMixin):
    """A series: a set of events that are scored together.

    "1st Sailing Bundesliga 2026", "Juniors 2026", "Sailing Champions League 2026". The
    name carries the year — a series **is** the competition for a given year. The earlier
    split into league and season was redundant: it always meant a given year's league
    anyway, and clubs had to be reassigned every year regardless.

    As a rule, the same clubs enter every event. If one misses an event, it gets
    **field size + 1** there — the same logic as an unsailed race, see
    ``app/services/standings.py``.

    Scoring parameters hang off the series, not the code: women's and youth series score
    differently, and regulations change between years.
    """

    __tablename__ = "series"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    # The full name including the year: "1st Sailing Bundesliga 2026".
    name: Mapped[str] = mapped_column(String(160))
    short_name: Mapped[str] = mapped_column(String(48))
    # For sorting and finding the current series.
    year: Mapped[int | None] = mapped_column(default=None, index=True)
    # The series' date range — same as for an event. Both are optional: when creating one,
    # often only the name is settled yet.
    starts_on: Mapped[date | None] = mapped_column(Date, default=None)
    ends_on: Mapped[date | None] = mapped_column(Date, default=None)
    # Rank within a year: 1 for the top division, 2 for the second.
    level: Mapped[int | None] = mapped_column(default=None)
    scoring: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # Whether the series is visible on the public site. A series is planned long before
    # anyone should see it: clubs get assigned, dates move, the name is still being argued
    # over. Publishing is therefore an explicit act — and it locks nothing, a published
    # series stays fully editable.
    published: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    # Free-text description for the public standings page, written and rendered as
    # Markdown. Longer than a club's — this is where the scoring can be explained, sponsors
    # thanked, or a season recapped, so `Text` rather than a bounded `String`.
    description: Mapped[str | None] = mapped_column(Text, default=None)

    events: Mapped[list[Event]] = relationship(back_populates="series")
    teams: Mapped[list[Team]] = relationship(back_populates="series")


class Venue(Base, TimestampMixin):
    __tablename__ = "venue"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    city: Mapped[str] = mapped_column(String(120))
    water: Mapped[str | None] = mapped_column(String(120), default=None)
    lat: Mapped[float | None] = mapped_column(Numeric(9, 6), default=None)
    lon: Mapped[float | None] = mapped_column(Numeric(9, 6), default=None)

    events: Mapped[list[Event]] = relationship(back_populates="venue")


class Event(Base, TimestampMixin):
    """An event.

    The normal case is an **act of a series**: then ``series_id`` and ``matchday`` are
    set, and the results count toward the series standings.

    But an event can also **stand on its own** — a cup, a training weekend, an invitational
    regatta. Then the series stays empty; it shows up in the calendar but flows into no
    series standings.
    """

    __tablename__ = "event"
    # Only applies to acts of a series; for standalone events these columns are NULL, and
    # multiple NULL combinations aren't considered equal in SQL.
    __table_args__ = (UniqueConstraint("series_id", "matchday"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    # Which act of the series this is. Only assigned for series events.
    matchday: Mapped[int | None] = mapped_column(default=None)

    # The matchday's format. Everything else follows from this: 18 teams on 6 boats means
    # 3 races per flight, 17 teams still 3 (with one empty slot), 12 teams on 6 boats
    # only 2.
    team_count: Mapped[int] = mapped_column(default=18)
    boat_count: Mapped[int] = mapped_column(default=6)
    flight_count: Mapped[int] = mapped_column(default=16)
    # How many people a club fields for this matchday. They must come from the team's
    # squad (Story V-2). A guideline, not a hard limit.
    crew_size: Mapped[int] = mapped_column(default=4)

    # Optional, like every other part of the setup: an event must be **savable while
    # incomplete** (a date still being negotiated with the host is the normal early
    # state). Missing dates are one of the reasons the event isn't ready to start yet —
    # see ``app/services/event_readiness.py``.
    starts_on: Mapped[date | None] = mapped_column(Date, default=None)
    ends_on: Mapped[date | None] = mapped_column(Date, default=None)
    status: Mapped[str] = mapped_column(String(16), default=EventStatus.PLANNED)
    # Public visibility, orthogonal to ``status``: an event is published when the calendar
    # entry should be readable, which is usually long before it goes ``live``, and
    # publishing never freezes anything. What freezes the setup is the **first race** —
    # see ``app/services/event_readiness.py::configuration_frozen``.
    published: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    # Empty when the event stands on its own.
    series_id: Mapped[int | None] = mapped_column(
        ForeignKey("series.id"), index=True, default=None
    )
    # The venue is often not yet settled when creating an event — the host and date
    # usually already are.
    venue_id: Mapped[int | None] = mapped_column(
        ForeignKey("venue.id"), index=True, default=None
    )
    # The hosting club. Not the same as the venue: DTYC hosts in Tutzing, but a club can
    # also host elsewhere.
    host_club_id: Mapped[int | None] = mapped_column(
        ForeignKey("club.id"), index=True, default=None
    )
    # The event's own logo. If missing, the host club's crest is shown instead.
    logo_url: Mapped[str | None] = mapped_column(String(300), default=None)

    # SAP Sailing access is a value per regatta, not a global secret.
    sap_leaderboard: Mapped[str | None] = mapped_column(String(200), default=None)

    @property
    def races_per_flight(self) -> int:
        """How many races a flight comprises, so every team sails exactly once."""
        if self.boat_count < 1:
            raise ValueError("A matchday needs at least one boat")
        return -(-self.team_count // self.boat_count)

    @property
    def races_total(self) -> int:
        return self.races_per_flight * self.flight_count

    series: Mapped[Series | None] = relationship(back_populates="events")
    venue: Mapped[Venue | None] = relationship(back_populates="events")
    host_club: Mapped[Club | None] = relationship()
    # The clubs entered in this event. The pairing list hangs off the event — and so do
    # the teams that appear in it.
    teams: Mapped[list[Team]] = relationship(back_populates="event")
    flights: Mapped[list[Flight]] = relationship(
        back_populates="event", cascade="all, delete-orphan", order_by="Flight.number"
    )
    boats: Mapped[list[Boat]] = relationship(
        back_populates="event", cascade="all, delete-orphan", order_by="Boat.number"
    )

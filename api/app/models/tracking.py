"""Boats on the water: the course laid, the phones on the boats, and their fixes.

Stories L-1 and L-2. What is stored is only what was *observed or decided*: where the
marks were set, which phone is on which boat, and every fix that arrived. Legs, passings,
distance to go and rank are derived from these on every read and never stored — the same
rule as points (``docs/PLAN_LIVE_IMPLEMENTATION.md``, decision 12).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Course(Base, TimestampMixin):
    """One laying of the windward/leeward course for an event.

    Re-laying creates a **new** row: races already started keep the ``course_id`` they were
    started with (``Race.course_id``), so a mark moved between races changes nothing about
    a race that is over. The newest row is the event's active course.
    """

    __tablename__ = "course"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("event.id"), index=True)
    laps: Mapped[int] = mapped_column(default=1)
    finish_upwind: Mapped[bool] = mapped_column(default=False)
    finish_pin_side: Mapped[str] = mapped_column(String(8), default="left")
    #: The committee's wind, typed in or taken from the axis when laid — in knots and degrees.
    tws_kn: Mapped[float | None] = mapped_column(default=None)
    wind_from_deg: Mapped[float | None] = mapped_column(default=None)

    marks: Mapped[list[Mark]] = relationship(
        back_populates="course", cascade="all, delete-orphan", order_by="Mark.role"
    )


class Mark(Base, TimestampMixin):
    """Where one mark of the course is: the committee boat, the pin, the windward mark, the
    two gate marks, the finish pin (``app.tracking.course.MarkRole``)."""

    __tablename__ = "mark"
    __table_args__ = (UniqueConstraint("course_id", "role"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("course.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    lat: Mapped[float]
    lon: Mapped[float]
    set_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    course: Mapped[Course] = relationship(back_populates="marks")


class Tracker(Base, TimestampMixin):
    """A device that sends fixes: the phone on a boat, or on the committee boat.

    **The tracker belongs to the boat, not the team** (decision 5): who sails boat 3 in race
    17 is what ``RaceEntry`` already says. The committee boat is a tracker too (decision 6):
    its position is the boat end of the start and finish lines. ``device_token`` is what a
    phone sends with every batch; issued from the race-control screen, never typed.
    """

    __tablename__ = "tracker"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("event.id"), index=True)
    boat_id: Mapped[int | None] = mapped_column(ForeignKey("boat.id"), default=None, index=True)
    mark_role: Mapped[str | None] = mapped_column(String(16), default=None)
    device_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    active_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    active_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    fixes: Mapped[list[Fix]] = relationship(back_populates="tracker", cascade="all, delete-orphan")


class Fix(Base):
    """One GPS fix. Speed in m/s, course in degrees true — SAP's units, and the phone's.

    About 170k rows per matchday. ``(tracker_id, t)`` is unique, which is what makes a
    retried batch idempotent. No ``TimestampMixin``: ``t`` is the only time that matters.
    """

    __tablename__ = "fix"
    __table_args__ = (UniqueConstraint("tracker_id", "t"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tracker_id: Mapped[int] = mapped_column(ForeignKey("tracker.id"), index=True)
    t: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    lat: Mapped[float]
    lon: Mapped[float]
    sog: Mapped[float]
    cog: Mapped[float]

    tracker: Mapped[Tracker] = relationship(back_populates="fixes")

"""Request and response models for administrative endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.public import BoatOut, TeamOut


class PairingJobRequest(BaseModel):
    """Job to calculate a pairing list (Story VA-3)."""

    flights: int = Field(default=16, ge=1, le=40)
    boats: int = Field(default=6, ge=2, le=20)
    seed: int = Field(default=1240, description="Makes the draw reproducible")
    effort: Literal["fast", "full"] = Field(
        default="full",
        description=(
            "'full' matches the setting for real matchdays and runs for many minutes. "
            "'fast' delivers a usable but poorer list in seconds."
        ),
    )


class JobOut(BaseModel):
    id: str
    kind: str
    status: str
    progress: float
    message: str
    error: str | None = None
    created_at: datetime
    finished_at: datetime | None = None
    # For completed pairing calculation the quality report, otherwise empty.
    quality: dict[str, Any] = Field(default_factory=dict)


class PairingImportRequest(BaseModel):
    """Import a list created elsewhere — for example from the Java tool."""

    schedule_config: str = Field(description="Content of schedule_cfg.yml")
    pairing_list: str = Field(description="Content of pairing_list.yml")


class PublishRequest(BaseModel):
    job_id: str


class PublishResult(BaseModel):
    boats: int
    flights: int
    races: int
    entries: int
    quality: dict[str, Any] = Field(default_factory=dict)


class RaceResultIn(BaseModel):
    """A result as recorded by the race officer."""

    boat_number: int
    code: str
    finish_position: int | None = None
    redress_points: float | None = None


class RaceResultsIn(BaseModel):
    results: list[RaceResultIn]
    # Version the submitter last saw. If it no longer matches, someone else changed this
    # race in the meantime — the later entry still wins, but the discarded state is
    # written to AuditLog first (see put_race_result) rather than silently dropped.
    #
    # No idempotency key: this endpoint is a PUT that fully re-applies the submitted
    # boats' results, so resubmitting the same payload is already safe on its own —
    # true double-submission protection only matters once offline queuing exists
    # (Story WL-1), and belongs here together with that, not as an unused field now.
    version: int | None = None


class RaceResultsOut(BaseModel):
    race_id: int
    sequence: int
    status: str
    version: int
    applied: bool
    overwrote_existing: bool = False
    note: str | None = None


class RaceEntryOut(BaseModel):
    """One boat's pairing and (if entered) result in a race, for the entry screen."""

    boat_number: int
    team: TeamOut
    code: str | None = None
    finish_position: int | None = None
    redress_points: float | None = None
    points: float | None = None
    is_discarded: bool = False


class AdminRaceOut(BaseModel):
    """A single race with pairing and current result state — Story WL-2."""

    id: int
    sequence: int
    flight: int
    race_in_flight: int
    status: str
    version: int
    entries: list[RaceEntryOut]


class AdminRacesOut(BaseModel):
    event_id: int
    boats: list[BoatOut]
    races: list[AdminRaceOut]

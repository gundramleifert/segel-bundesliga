"""The jury pool's requests and answers (Stories JU-1–JU-5)."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models import EventStatus, JudgeLicence, JuryState


class JudgeIn(BaseModel):
    user_id: int


class JudgeOut(BaseModel):
    """A judge in the pool, with their state at each event the table shows."""

    user_id: int
    name: str
    email: str
    licences: list[JudgeLicence]
    states: dict[str, JuryState] = Field(
        description="Per event asked for (`events`), by its id: the judge's state there; "
        "an event they were never asked for is missing"
    )


class CandidateOut(BaseModel):
    """An account the jury organizer may put in the pool."""

    user_id: int
    name: str
    email: str


class JuryEventOut(BaseModel):
    id: int
    title: str
    starts_on: date | None
    ends_on: date | None
    status: EventStatus
    published: bool
    series: str | None = Field(default=None, description="The series' short name")


class InvitationsIn(BaseModel):
    event_ids: list[int] = Field(min_length=1)
    user_ids: list[int]
    note: str | None = Field(default=None, max_length=2000)


class InvitationsOut(BaseModel):
    created: int = Field(description="Pairs newly asked")
    existing: int = Field(description="Pairs asked before, left as they were")
    mailed: int = Field(description="Judges written to — one mail each")


class MessageIn(BaseModel):
    user_ids: list[int] = Field(min_length=1)
    subject: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=5000)


class MessageOut(BaseModel):
    mailed: int


class JuryRequestOut(BaseModel):
    event: JuryEventOut
    user_id: int
    state: JuryState
    invited_at: datetime | None
    answered_at: datetime | None


class MyJuryOut(BaseModel):
    """*Me › Jury*: am I a judge, my licences, the events I was asked for."""

    judge: bool
    licences: list[JudgeLicence]
    requests: list[JuryRequestOut]


class LicencesIn(BaseModel):
    licences: list[JudgeLicence]


class AnswerIn(BaseModel):
    available: bool = Field(description="True: I can (my application). False: I cannot.")

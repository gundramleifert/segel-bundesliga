"""Feedback — Stories S-9 (anyone signed in sends it, from the page they are on) and A-15
(the site's ``feedback_receiver``s, and its admin, read it in the league office; the
receivers are mailed each one). The queries are `app/services/feedback.py`'s.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_user, require_site
from app.db import get_session
from app.filters import FeedbackFilter
from app.listing import ListDepends
from app.models import FEEDBACK_MAX_LENGTH, Feedback, FeedbackCategory
from app.models.auth import Relation, User
from app.pagination import Page, PageInput, PageParams, page_of, paginate
from app.problems import Problem
from app.services import feedback

router = APIRouter(tags=["feedback"])

# The admin passes through the model (`feedback_receiver: [user] or admin`).
require_feedback_reader = require_site(Relation.FEEDBACK_RECEIVER)


class FeedbackIn(BaseModel):
    category: FeedbackCategory
    # No ``min_length``: an empty message and a blank one get the same typed answer.
    message: str = Field(max_length=FEEDBACK_MAX_LENGTH)
    # An address inside the site — the admin's list links to it, so never another host
    # (``//host``, ``/\host`` and ``https://…`` are all refused).
    path: str = Field(max_length=2000, pattern=r"^/([^/\\].*)?$")
    locale: str = Field(default="", max_length=16)
    app_version: str = Field(default="", max_length=64)
    viewport_width: int | None = Field(default=None, ge=0, le=100_000)
    viewport_height: int | None = Field(default=None, ge=0, le=100_000)

    @field_validator("message")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class FeedbackOut(BaseModel):
    id: int
    category: FeedbackCategory
    message: str
    path: str
    created_at: datetime
    name: str = Field(description="The sender's name, from the account")
    email: str = Field(description="The sender's address, from the account")
    locale: str
    app_version: str
    viewport_width: int | None
    viewport_height: int | None
    user_agent: str
    handled: bool

    @classmethod
    def of(cls, row: Feedback) -> FeedbackOut:
        return cls(
            id=row.id,
            category=FeedbackCategory(row.category),
            message=row.message,
            path=row.path,
            created_at=row.created_at,
            name=row.user.display_name,
            email=row.user.email,
            locale=row.locale,
            app_version=row.app_version,
            viewport_width=row.viewport_width,
            viewport_height=row.viewport_height,
            user_agent=row.user_agent,
            handled=row.handled,
        )


class HandledIn(BaseModel):
    handled: bool


@router.post(
    "/api/feedback",
    response_model=FeedbackOut,
    status_code=status.HTTP_201_CREATED,
    summary="Send feedback",
)
async def send_feedback(
    body: FeedbackIn,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> FeedbackOut:
    """Story S-9: anyone signed in. The browser is the request's ``User-Agent``; the rest
    of the context is what the page knew. Mailed to the site's feedback receivers after
    it is stored — none, and it is stored all the same (Story A-15)."""
    if not body.message:
        raise Problem(422, "feedback-message-empty", "Feedback needs a message.")
    row = await feedback.record(
        session,
        user,
        feedback.Sent(
            category=body.category,
            message=body.message,
            path=body.path,
            locale=body.locale,
            app_version=body.app_version,
            viewport_width=body.viewport_width,
            viewport_height=body.viewport_height,
            user_agent=request.headers.get("user-agent", ""),
        ),
    )
    await feedback.notify(session, row)
    return FeedbackOut.of(row)


@router.get(
    "/api/admin/feedback",
    response_model=Page[FeedbackOut],
    dependencies=[Depends(require_feedback_reader)],
    summary="List feedback",
)
async def list_feedback(
    filters: FeedbackFilter = ListDepends(FeedbackFilter),
    params: PageParams = PageInput,
    session: AsyncSession = Depends(get_session),
) -> Page[FeedbackOut]:
    """Story A-15: newest first, filtered by kind and handled on the server."""
    rows, total = await paginate(session, filters.sort(filters.filter(feedback.listing())), params)
    return page_of([FeedbackOut.of(row) for row in rows], total, params)


@router.patch(
    "/api/admin/feedback/{feedback_id}",
    response_model=FeedbackOut,
    dependencies=[Depends(require_feedback_reader)],
    summary="Mark feedback handled or open",
)
async def mark_feedback(
    feedback_id: int,
    body: HandledIn,
    session: AsyncSession = Depends(get_session),
) -> FeedbackOut:
    """Story A-15: a flag, not a workflow — the answer goes by mail, outside the site."""
    return FeedbackOut.of(await feedback.set_handled(session, feedback_id, body.handled))

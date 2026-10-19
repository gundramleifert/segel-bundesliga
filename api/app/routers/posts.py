"""News and press releases — Story R-1.

Editorial writes them here; the public site reads them through ``GET /api/posts``. Who
may write is the site's ``editor`` relation, which its ``admin`` holds through the model
(Story Z-2) — nobody else, not even an event's organizer: announcements from an event
are Story VA-11, posts by participants VA-4.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import require_editor
from app.db import get_session
from app.models import League, Post, PostKind
from app.models.auth import User
from app.pagination import Page, PageInput, PageParams, apply_search, page_of, paginate
from app.problems import Problem
from app.services.lookup import get_or_404, unique_slug
from app.services.rich_text import clean_html, repeats_title

router = APIRouter(prefix="/api/posts", tags=["posts"])
admin_router = APIRouter(prefix="/api/admin/posts", tags=["admin"])


class PostSummary(BaseModel):
    """A post as a list shows it — a card or a line: no text, which only its own page
    reads. A list of a few dozen posts need not carry each one's whole article."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: PostKind
    slug: str
    title: str
    published_on: date
    league_id: int | None = None
    league: str | None = Field(
        default=None,
        validation_alias="league_slug",
        description="The league's slug; empty for the association's own posts.",
    )
    teaser: str | None = None
    photo_url: str | None = None
    photo_credit: str | None = None
    example: bool = False


class PostOut(PostSummary):
    """A post as its own page shows it."""

    body: str = Field(description="HTML from the editor, cleaned to its few elements on write.")
    author: str | None = None
    quote: str | None = None
    quote_by: str | None = None


class PostAdminSummary(PostSummary):
    published: bool


class PostAdminOut(PostOut):
    published: bool


# Each limit once, for creating and correcting alike — the columns' sizes (`Post`).
Title = Annotated[str, Field(min_length=3, max_length=200)]
Body = Annotated[str, Field(max_length=50_000)]
Lead = Annotated[str | None, Field(max_length=500)]
Name = Annotated[str | None, Field(max_length=120)]
PhotoUrl = Annotated[str | None, Field(max_length=500)]
Credit = Annotated[str | None, Field(max_length=160)]


class PostFields(BaseModel):
    """What editorial writes — the same rules for creating and correcting. Surrounding
    whitespace is a typo, so it is stripped before any length is checked: a title of
    blanks is too short, not empty."""

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("teaser", "author", "quote", "quote_by", "photo_credit", check_fields=False)
    @classmethod
    def _none_if_empty(cls, value: str | None) -> str | None:
        """An emptied optional field means "none"."""
        return value or None

    @field_validator("body", check_fields=False)
    @classmethod
    def _clean(cls, value: str) -> str:
        """HTML from the editor, reduced to what its toolbar makes — see `rich_text`."""
        return clean_html(value)


class PostCreate(PostFields):
    kind: PostKind = PostKind.NEWS
    title: Title
    published_on: date | None = Field(default=None, description="The date shown; today if absent.")
    league_id: int | None = Field(
        default=None, description="The league it belongs to; empty for the association's."
    )
    teaser: Lead = None
    body: Body = ""
    author: Name = None
    quote: Lead = None
    quote_by: Name = None
    photo_url: PhotoUrl = None
    photo_credit: Credit = None
    published: bool = Field(default=False, description="Drafts are invisible on the public site.")


class PostUpdate(PostFields):
    """Only what is sent changes. The slug is not here: it is made once (Story R-1).

    The required columns default to ``None`` only so that they may be left out: an explicit
    ``null`` for one of them is a 422, never silently ignored."""

    kind: PostKind = None  # type: ignore[assignment]
    title: Title = None  # type: ignore[assignment]
    published_on: date = None  # type: ignore[assignment]
    league_id: int | None = None
    teaser: Lead = None
    body: Body = None  # type: ignore[assignment]
    author: Name = None
    quote: Lead = None
    quote_by: Name = None
    photo_url: PhotoUrl = None
    photo_credit: Credit = None
    published: bool = None  # type: ignore[assignment]


# ---------------------------------------------------------------- public


def _with_league():
    return select(Post).options(selectinload(Post.league))


@router.get("", response_model=list[PostSummary], summary="Published news or press releases")
async def list_posts(
    kind: PostKind = Query(default=PostKind.NEWS),
    league: str | None = Query(
        default=None,
        description="A league's slug: its posts and the association's. Absent: every post.",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[PostSummary]:
    """Newest first, without their text — that is ``GET /api/posts/{slug}``. Drafts never
    appear here."""
    stmt = _with_league().where(Post.published.is_(True), Post.kind == kind)
    if league is not None:
        stmt = stmt.outerjoin(League, Post.league_id == League.id).where(
            or_(Post.league_id.is_(None), League.slug == league)
        )
    stmt = stmt.order_by(Post.published_on.desc(), Post.id.desc()).limit(limit)
    posts = (await session.execute(stmt)).scalars().all()
    return [PostSummary.model_validate(post) for post in posts]


@router.get("/{slug}", response_model=PostOut, summary="One published post")
async def get_post(slug: str, session: AsyncSession = Depends(get_session)) -> PostOut:
    """A draft answers 404, like a draft event (Story VA-8)."""
    post = (
        await session.execute(_with_league().where(Post.slug == slug, Post.published.is_(True)))
    ).scalar_one_or_none()
    if post is None:
        raise Problem(404, "post-not-found", "No such post.", slug=slug)
    return PostOut.model_validate(post)


# ---------------------------------------------------------------- editorial

POST_SORT = {"published_on": Post.published_on, "title": Post.title}


@admin_router.get("", response_model=Page[PostAdminSummary], summary="All posts, drafts included")
async def list_all_posts(
    kind: PostKind | None = Query(default=None),
    q: str | None = Query(default=None, description="Search in the title"),
    params: PageParams = PageInput,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_editor),
) -> Page[PostAdminSummary]:
    stmt = apply_search(_with_league(), q, Post.title)
    if kind is not None:
        stmt = stmt.where(Post.kind == kind)
    posts, total = await paginate(
        session,
        stmt,
        params,
        sortable=POST_SORT,
        default_order=[Post.published_on.desc(), Post.id.desc()],
    )
    return page_of([PostAdminSummary.model_validate(post) for post in posts], total, params)


@admin_router.post(
    "", response_model=PostAdminOut, status_code=status.HTTP_201_CREATED, summary="Write a post"
)
async def create_post(
    body: PostCreate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_editor),
) -> PostAdminOut:
    """A draft unless ``published`` says otherwise. The slug is made from the title."""
    await _check_league(session, body.league_id)
    _title_not_in_text(body.title, body.body)
    fields = body.model_dump()
    fields["published_on"] = fields["published_on"] or date.today()
    # Cut before the slug is made, so a long title's slug still fits with a number added.
    post = Post(**fields, slug=await unique_slug(session, Post, body.title[:100]))
    session.add(post)
    await session.commit()
    return await _admin_out(session, post)


@admin_router.get("/{post_id}", response_model=PostAdminOut, summary="One post, draft or not")
async def get_admin_post(
    post_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_editor),
) -> PostAdminOut:
    return await _admin_out(session, await get_or_404(session, Post, post_id))


@admin_router.patch("/{post_id}", response_model=PostAdminOut, summary="Correct a post")
async def update_post(
    post_id: int,
    body: PostUpdate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_editor),
) -> PostAdminOut:
    """Publishing and withdrawing are a change of ``published`` — nothing is locked."""
    post = await get_or_404(session, Post, post_id)
    changes = body.model_dump(exclude_unset=True)
    # The title and the text as they will be: a new title alone may repeat the text too.
    _title_not_in_text(changes.get("title", post.title), changes.get("body", post.body))
    if "league_id" in changes:
        await _check_league(session, changes["league_id"])
    for name, value in changes.items():
        setattr(post, name, value)
    await session.commit()
    return await _admin_out(session, post)


@admin_router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a post")
async def delete_post(
    post_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_editor),
) -> Response:
    post = await get_or_404(session, Post, post_id)
    await session.delete(post)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- helpers


async def _admin_out(session: AsyncSession, post: Post) -> PostAdminOut:
    """The post as editorial sees it, its league (re)loaded — it may just have changed."""
    await session.refresh(post, ["league"])
    return PostAdminOut.model_validate(post)


def _title_not_in_text(title: str, body: str) -> None:
    if repeats_title(body, title):
        raise Problem(
            422,
            "post-title-in-text",
            "The text starts with the title again.",
            detail="The title is shown above the text; start the text with what follows it.",
        )


async def _check_league(session: AsyncSession, league_id: int | None) -> None:
    if league_id is not None:
        await get_or_404(session, League, league_id)

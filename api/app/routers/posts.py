"""News and press releases — Story R-1.

Editorial writes them here; the public site reads them through ``GET /api/posts``. Who
may write is the ``editor`` relation (Story Z-2, decided 2026-10-24): the site's for every
post, a series' or an event's for posts about that regatta, which then appear in its
league (``app/services/editorial.py``). Not an event's organizer: announcements from an
event are Story VA-11, posts by participants VA-4.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import require_any_editor
from app.db import get_session
from app.filters import PostFilter, PublicPostFilter
from app.listing import ListDepends
from app.models import Event, League, MediaItem, Post, PostKind, Series
from app.models.auth import User
from app.pagination import (
    Page,
    PageInput,
    PageParams,
    page_of,
    paginate,
)
from app.problems import Problem
from app.routers.media import PublicPicture, public_picture
from app.services import editorial, media
from app.services.lookup import get_or_404, unique_slug
from app.services.rich_text import clean_html, outside_pictures, own_picture, repeats_title

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
    league_name: str | None = Field(
        default=None, description="The league's short name; empty for the association's."
    )
    teaser: str | None = None
    photo_url: str | None = None
    photo_srcset: str | None = Field(
        default=None, description="The picture's sizes, when it is the library's."
    )
    photo_credit: str | None = None
    example: bool = False


#: How many of its regatta's pictures a post's page shows; the rest are on the media page.
GALLERY_SIZE = 24


class PostOut(PostSummary):
    """A post as its own page shows it."""

    body: str = Field(description="HTML from the editor, cleaned to its few elements on write.")
    author: str | None = None
    quote: str | None = None
    quote_by: str | None = None
    event_id: int | None = None
    series_id: int | None = None
    regatta: str | None = Field(default=None, description="The event's title or series' name.")
    gallery: list[PublicPicture] = Field(
        default_factory=list,
        description=f"Its regatta's public pictures, the first {GALLERY_SIZE}.",
    )
    gallery_total: int = Field(default=0, description="How many the regatta has in all.")


class PostAdminSummary(PostSummary):
    published: bool
    updated_at: datetime


class PostAdminOut(PostOut):
    published: bool
    updated_at: datetime = Field(description="When it was last saved — to tell a device's copy.")


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
    event_id: int | None = Field(default=None, description="The event it is about.")
    series_id: int | None = Field(default=None, description="The series it is about.")
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
    event_id: int | None = Field(default=None, description="Sent: it is about this event.")
    series_id: int | None = Field(default=None, description="Sent: it is about this series.")
    published: bool = None  # type: ignore[assignment]


# ---------------------------------------------------------------- public


def _with_league():
    return select(Post).options(selectinload(Post.league))


@router.get("", response_model=Page[PostSummary], summary="Published news or press releases")
async def list_posts(
    kind: PostKind = Query(default=PostKind.NEWS),
    league: str | None = Query(
        default=None,
        description="A league's slug: its posts and the association's. Absent: every post.",
    ),
    filters: PublicPostFilter = ListDepends(PublicPostFilter),
    params: PageParams = PageInput,
    session: AsyncSession = Depends(get_session),
) -> Page[PostSummary]:
    """Newest first, a page at a time, without their text — that is
    ``GET /api/posts/{slug}``. Drafts never appear here."""
    stmt = _with_league().where(Post.published.is_(True), Post.kind == kind)
    if league is not None:
        stmt = stmt.outerjoin(League, Post.league_id == League.id).where(
            or_(Post.league_id.is_(None), League.slug == league)
        )
    posts, total = await paginate(session, filters.sort(stmt), params)
    return page_of(await _summaries(session, posts, PostSummary), total, params)


@router.get("/{slug}", response_model=PostOut, summary="One published post")
async def get_post(slug: str, session: AsyncSession = Depends(get_session)) -> PostOut:
    """A draft answers 404, like a draft event (Story VA-8). The text's pictures come with
    the library's alt text, sizes and credit (`media.for_readers`)."""
    post = (
        await session.execute(_with_league().where(Post.slug == slug, Post.published.is_(True)))
    ).scalar_one_or_none()
    if post is None:
        raise Problem(404, "post-not-found", "No such post.", slug=slug)
    return await _for_readers(session, post)


# ---------------------------------------------------------------- editorial


@admin_router.get("", response_model=Page[PostAdminSummary], summary="All posts, drafts included")
async def list_all_posts(
    filters: PostFilter = ListDepends(PostFilter),
    params: PageParams = PageInput,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_any_editor),
) -> Page[PostAdminSummary]:
    """Every post this person may change — the site's editor all of them, a regatta's
    editor that regatta's, whoever wrote them (Story R-1)."""
    stmt = filters.filter(_with_league())
    reach = editorial.within_reach(user, Post.event_id, Post.series_id)
    if reach is not None:
        stmt = stmt.where(reach)
    posts, total = await paginate(session, filters.sort(stmt), params)
    return page_of(await _summaries(session, posts, PostAdminSummary), total, params)


@admin_router.post(
    "", response_model=PostAdminOut, status_code=status.HTTP_201_CREATED, summary="Write a post"
)
async def create_post(
    body: PostCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_any_editor),
) -> PostAdminOut:
    """A draft unless ``published`` says otherwise. The slug is made from the title."""
    await _check_about(session, user, body)
    _title_not_in_text(body.title, body.body)
    _pictures_are_ours(body.body, body.photo_url)
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
    user: User = Depends(require_any_editor),
) -> PostAdminOut:
    return await _admin_out(session, await _own_post(session, user, post_id))


@admin_router.post("/preview", response_model=PostOut, summary="A post as readers will see it")
async def preview_post(
    body: PostCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_any_editor),
) -> PostOut:
    """What ``GET /api/posts/{slug}`` would answer for these fields — saved or not, so a
    draft is read before it is saved and a published post's edit before it goes live.
    Nothing is stored; the same rules as a save apply."""
    await _check_about(session, user, body)
    _title_not_in_text(body.title, body.body)
    _pictures_are_ours(body.body, None)
    fields = body.model_dump(exclude={"published"})
    post = Post(**fields, id=0, slug="preview", published=False, example=False)
    post.published_on = post.published_on or date.today()
    post.league = await session.get(League, body.league_id) if body.league_id else None
    return await _for_readers(session, post)


@admin_router.patch("/{post_id}", response_model=PostAdminOut, summary="Correct a post")
async def update_post(
    post_id: int,
    body: PostUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_any_editor),
) -> PostAdminOut:
    """Publishing and withdrawing are a change of ``published`` — nothing is locked."""
    post = await _own_post(session, user, post_id)
    changes = body.model_dump(exclude_unset=True)
    # The title and the text as they will be: a new title alone may repeat the text too.
    _title_not_in_text(changes.get("title", post.title), changes.get("body", post.body))
    # An address the post already has may stay: the seeded examples link the league's
    # own photos, and correcting a typo in one must not need a new picture.
    photo = changes.get("photo_url")
    _pictures_are_ours(changes.get("body", ""), None if photo == post.photo_url else photo)
    if "league_id" in changes:
        await _check_league(session, changes["league_id"])
    if "event_id" in changes or "series_id" in changes:
        # One of them is what the post is about; sending one replaces the other.
        changes.setdefault("event_id", None)
        changes.setdefault("series_id", None)
        await media.check_context(session, changes["event_id"], changes["series_id"])
        await editorial.ensure_about(session, user, changes["event_id"], changes["series_id"])
    if not editorial.site_editor(user):
        # A regatta's editor writes in its league, wherever the post says it is about.
        changes["league_id"] = await editorial.league_of(
            session,
            changes.get("event_id", post.event_id),
            changes.get("series_id", post.series_id),
        )
    for name, value in changes.items():
        setattr(post, name, value)
    await session.commit()
    return await _admin_out(session, post)


@admin_router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a post")
async def delete_post(
    post_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_any_editor),
) -> Response:
    post = await _own_post(session, user, post_id)
    await session.delete(post)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- helpers


async def _check_about(session: AsyncSession, user: User, body: PostCreate) -> None:
    """The league and the regatta exist, and this person writes about that regatta. A
    regatta's editor writes in its league: ``league_id`` is set from it, not chosen."""
    await media.check_context(session, body.event_id, body.series_id)
    await editorial.ensure_about(session, user, body.event_id, body.series_id)
    if not editorial.site_editor(user):
        body.league_id = await editorial.league_of(session, body.event_id, body.series_id)
    await _check_league(session, body.league_id)


async def _own_post(session: AsyncSession, user: User, post_id: int) -> Post:
    """The post, if this person writes about its regatta — another regatta's post is a
    404 to them, like one that does not exist: its draft is not theirs to know of."""
    post = await get_or_404(session, Post, post_id)
    if not editorial.site_editor(user):
        try:
            await editorial.ensure_about(session, user, post.event_id, post.series_id)
        except Problem:
            raise Problem(404, "post-not-found", "No such post.") from None
    return post


async def _admin_out(session: AsyncSession, post: Post) -> PostAdminOut:
    """The post as editorial sees it, its league (re)loaded — it may just have changed."""
    await session.refresh(post, ["league", "updated_at"])
    (shown,) = await _shown(session, [post])
    return PostAdminOut.model_validate(post).model_copy(update=shown)


async def _shown(session: AsyncSession, posts: list[Post]) -> list[dict[str, str | None]]:
    """What each post shows beside its columns: its league's name and, for a library
    picture, its sizes. Load ``league`` first."""
    names = {name for post in posts if (name := media.name_in(post.photo_url))}
    pictures = await media.by_name(session, names)
    shown = []
    for post in posts:
        item = pictures.get(media.name_in(post.photo_url) or "")
        shown.append(
            {
                "league_name": post.league.short_name if post.league else None,
                "photo_srcset": media.srcset(item) if item else None,
            }
        )
    return shown


async def _summaries[T: PostSummary](
    session: AsyncSession, posts: list[Post], model: type[T]
) -> list[T]:
    shown = await _shown(session, posts)
    return [
        model.model_validate(post).model_copy(update=extra)
        for post, extra in zip(posts, shown, strict=True)
    ]


async def _for_readers(session: AsyncSession, post: Post) -> PostOut:
    """The post as its public page shows it: the text's pictures from the library, and the
    gallery of the regatta it names. Load ``league`` first."""
    (shown,) = await _shown(session, [post])
    gallery = media.public_of(post.event_id, post.series_id)
    total = await session.scalar(
        select(func.count()).select_from(gallery.order_by(None).subquery())
    )
    rows = await session.execute(
        gallery.options(selectinload(MediaItem.event), selectinload(MediaItem.series)).limit(
            GALLERY_SIZE
        )
    )
    event = await session.get(Event, post.event_id) if post.event_id else None
    series = await session.get(Series, post.series_id) if post.series_id else None
    extra = {
        **shown,
        "body": await media.for_readers(session, post.body),
        "gallery": [public_picture(item) for item in rows.scalars()],
        "gallery_total": total or 0,
        "regatta": event.title if event else (series.name if series else None),
    }
    return PostOut.model_validate(post).model_copy(update=extra)


def _pictures_are_ours(body: str, photo_url: str | None) -> None:
    """Refuses a picture from someone else's server — in the text or as the post's own."""
    outside = outside_pictures(body)
    if photo_url and not own_picture(photo_url):
        outside.append(photo_url)
    if outside:
        raise Problem(
            422,
            "post-picture-not-in-library",
            "A picture is not in the library.",
            detail="Pictures are copied into the library, never linked from another site.",
            addresses=outside,
        )


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

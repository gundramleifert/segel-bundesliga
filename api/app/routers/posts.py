"""News and press releases — Story R-1.

Editorial writes them here; the public site reads them through ``GET /api/posts``. Who
may write is the site's ``editor`` relation, which its ``admin`` holds through the model
(Story Z-2) — nobody else, not even an event's organizer: announcements from an event
are Story VA-11, posts by participants VA-4.
"""

from __future__ import annotations

import asyncio
import io
import uuid
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import require_editor
from app.config import settings
from app.db import get_session
from app.models import League, Post, PostKind
from app.models.auth import User
from app.pagination import Page, PageInput, PageParams, apply_search, page_of, paginate
from app.problems import Problem
from app.services.lookup import get_or_404
from app.services.rich_text import clean_html
from app.services.uploads import validated
from app.text import slugify

router = APIRouter(prefix="/api/posts", tags=["posts"])
admin_router = APIRouter(prefix="/api/admin/posts", tags=["admin"])

# A picture for the web, not an archive: the longest edge a card or a page header needs,
# re-encoded so a phone's EXIF (location included) never reaches the public site.
_PHOTO_EDGE = 2000
_JPEG_QUALITY = 85


class PostOut(BaseModel):
    """A post as the public site shows it."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: PostKind
    slug: str
    title: str
    published_on: date
    league_id: int | None = None
    league: str | None = Field(
        default=None, description="The league's slug; empty for the association's own posts."
    )
    teaser: str | None = None
    body: str = Field(description="HTML from the editor, cleaned to its few elements on write.")
    author: str | None = None
    quote: str | None = None
    quote_by: str | None = None
    photo_url: str | None = None
    photo_credit: str | None = None
    example: bool = False


class PostAdminOut(PostOut):
    published: bool


def _out[T: PostOut](post: Post, schema: type[T]) -> T:
    return schema.model_validate(
        {
            **{name: getattr(post, name) for name in schema.model_fields if name != "league"},
            "league": post.league.slug if post.league else None,
        }
    )


class PostFields(BaseModel):
    """What editorial writes — the same rules for creating and correcting."""

    @field_validator(
        "title",
        "teaser",
        "author",
        "quote",
        "quote_by",
        "photo_credit",
        mode="after",
        check_fields=False,
    )
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        """Surrounding whitespace is a typo; an emptied optional field means "none"."""
        if value is None:
            return None
        return value.strip() or None

    @field_validator("body", mode="after", check_fields=False)
    @classmethod
    def _clean(cls, value: str | None) -> str | None:
        """HTML from the editor, reduced to what its toolbar makes — see `rich_text`."""
        return None if value is None else clean_html(value)


class PostCreate(PostFields):
    kind: PostKind = PostKind.NEWS
    title: str = Field(min_length=3, max_length=200)
    published_on: date | None = Field(default=None, description="The date shown; today if absent.")
    league_id: int | None = Field(
        default=None, description="The league it belongs to; empty for the association's."
    )
    teaser: str | None = Field(default=None, max_length=500)
    body: str = Field(default="", max_length=50_000)
    author: str | None = Field(default=None, max_length=120)
    quote: str | None = Field(default=None, max_length=500)
    quote_by: str | None = Field(default=None, max_length=120)
    photo_url: str | None = Field(default=None, max_length=500)
    photo_credit: str | None = Field(default=None, max_length=160)
    published: bool = Field(default=False, description="Drafts are invisible on the public site.")


class PostUpdate(PostFields):
    """Only what is sent changes. The slug is not here: it is made once (Story R-1)."""

    kind: PostKind | None = None
    title: str | None = Field(default=None, min_length=3, max_length=200)
    published_on: date | None = None
    league_id: int | None = None
    teaser: str | None = Field(default=None, max_length=500)
    body: str | None = Field(default=None, max_length=50_000)
    author: str | None = Field(default=None, max_length=120)
    quote: str | None = Field(default=None, max_length=500)
    quote_by: str | None = Field(default=None, max_length=120)
    photo_url: str | None = Field(default=None, max_length=500)
    photo_credit: str | None = Field(default=None, max_length=160)
    published: bool | None = None


class PhotoOut(BaseModel):
    url: str


# ---------------------------------------------------------------- public


def _with_league():
    return select(Post).options(selectinload(Post.league))


@router.get("", response_model=list[PostOut], summary="Published news or press releases")
async def list_posts(
    kind: PostKind = Query(default=PostKind.NEWS),
    league: str | None = Query(
        default=None,
        description="A league's slug: its posts and the association's. Absent: every post.",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[PostOut]:
    """Newest first. Drafts never appear here."""
    stmt = _with_league().where(Post.published.is_(True), Post.kind == kind)
    if league is not None:
        stmt = stmt.outerjoin(League, Post.league_id == League.id).where(
            or_(Post.league_id.is_(None), League.slug == league)
        )
    stmt = stmt.order_by(Post.published_on.desc(), Post.id.desc()).limit(limit)
    posts = (await session.execute(stmt)).scalars().all()
    return [_out(post, PostOut) for post in posts]


@router.get("/photos/{name}", summary="A post's uploaded picture")
async def get_post_photo(name: str) -> FileResponse:
    """Public: a picture is uploaded to be shown. The name is random, never a path."""
    path = _photo_dir() / name
    if path.parent != _photo_dir() or not path.is_file():
        raise Problem(404, "post-photo-not-found", "No such picture.")
    return FileResponse(path, media_type="image/jpeg")


@router.get("/{slug}", response_model=PostOut, summary="One published post")
async def get_post(slug: str, session: AsyncSession = Depends(get_session)) -> PostOut:
    """A draft answers 404, like a draft event (Story VA-8)."""
    post = (
        await session.execute(_with_league().where(Post.slug == slug, Post.published.is_(True)))
    ).scalar_one_or_none()
    if post is None:
        raise Problem(404, "post-not-found", "No such post.", slug=slug)
    return _out(post, PostOut)


# ---------------------------------------------------------------- editorial

POST_SORT = {"published_on": Post.published_on, "title": Post.title}


@admin_router.get("", response_model=Page[PostAdminOut], summary="All posts, drafts included")
async def list_all_posts(
    kind: PostKind | None = Query(default=None),
    q: str | None = Query(default=None, description="Search in the title"),
    params: PageParams = PageInput,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_editor),
) -> Page[PostAdminOut]:
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
    return page_of([_out(post, PostAdminOut) for post in posts], total, params)


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
    fields = body.model_dump()
    fields["published_on"] = fields["published_on"] or date.today()
    post = Post(**fields, slug=await _free_slug(session, body.title))
    session.add(post)
    await session.commit()
    return await _admin_out(session, post.id)


@admin_router.get("/{post_id}", response_model=PostAdminOut, summary="One post, draft or not")
async def get_admin_post(
    post_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_editor),
) -> PostAdminOut:
    return await _admin_out(session, post_id)


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
    if "league_id" in changes:
        await _check_league(session, changes["league_id"])
    for required in ("kind", "title", "published_on", "body", "published"):
        if required in changes and changes[required] is None:
            del changes[required]
    for name, value in changes.items():
        setattr(post, name, value)
    await session.commit()
    return await _admin_out(session, post_id)


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


@admin_router.post("/photo", response_model=PhotoOut, summary="Upload a picture for a post")
async def upload_post_photo(
    file: UploadFile = File(...),
    _: User = Depends(require_editor),
) -> PhotoOut:
    """A JPEG or PNG, checked by content, re-encoded and stored under a random name. The
    answer is the address to put in a post's ``photo_url``."""
    raw = await file.read()
    content_type = await validated(raw, file.content_type, code="post-photo", what="The picture")
    if content_type == "application/pdf":
        raise Problem(422, "post-photo-invalid-type", "The picture must be a JPEG or a PNG.")
    name = f"{uuid.uuid4().hex}.jpg"
    await asyncio.to_thread(_save_photo, raw, _photo_dir() / name)
    return PhotoOut(url=f"/api/posts/photos/{name}")


# ---------------------------------------------------------------- helpers


async def _admin_out(session: AsyncSession, post_id: int) -> PostAdminOut:
    post = (
        await session.execute(
            _with_league().where(Post.id == post_id).execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if post is None:
        raise Problem(404, "post-not-found", f"Post {post_id} not found.", id=post_id)
    return _out(post, PostAdminOut)


async def _check_league(session: AsyncSession, league_id: int | None) -> None:
    if league_id is not None:
        await get_or_404(session, League, league_id)


async def _free_slug(session: AsyncSession, title: str) -> str:
    """The title's slug, numbered if another post already has it — never overwritten."""
    base = slugify(title)[:100]
    taken = set(
        (await session.execute(select(Post.slug).where(Post.slug.like(f"{base}%")))).scalars()
    )
    if base not in taken:
        return base
    number = 2
    while f"{base}-{number}" in taken:
        number += 1
    return f"{base}-{number}"


def _photo_dir() -> Path:
    return Path(settings.uploads_dir).resolve() / "posts"


def _save_photo(raw: bytes, path: Path) -> None:
    from PIL import Image, ImageOps

    image = Image.open(io.BytesIO(raw))
    image = (ImageOps.exif_transpose(image) or image).convert("RGB")
    image.thumbnail((_PHOTO_EDGE, _PHOTO_EDGE), Image.LANCZOS)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="JPEG", quality=_JPEG_QUALITY)

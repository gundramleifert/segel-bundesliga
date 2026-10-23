"""The picture library and its import API — Story R-2, `docs/PLAN_MEDIA.md`.

Three doors, each with its own guard:

* ``/api/admin/media``, ``/api/admin/import-keys`` — editorial (the site's ``editor``,
  and its ``admin`` through the model), like posts (Story R-1);
* ``/api/import`` — a **source**, with an import key in ``X-Import-Key`` and no person
  signed in: our upload page first, later a Nextcloud or Flickr bridge. Every source uses
  these two endpoints and nothing else;
* ``/api/media/<name>.webp`` — everyone: a picture is stored to be shown, and its random
  name is the only way to it.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Header, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import require_editor
from app.db import get_session
from app.models import ImportKey, MediaItem, MediaSource
from app.models.auth import User
from app.models.base import utcnow
from app.models.editorial import context_of
from app.pagination import Page, PageInput, PageParams, apply_search, page_of, paginate
from app.problems import Problem
from app.services import media
from app.services.lookup import get_or_404

admin_router = APIRouter(prefix="/api/admin", tags=["media"])
import_router = APIRouter(prefix="/api/import", tags=["import"])
public_router = APIRouter(prefix="/api/media", tags=["media"])


class MediaOut(BaseModel):
    """A picture in the library."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str = Field(description="The picture, at most 2400 px — what a post points at.")
    thumb_url: str = Field(description="A small copy for the library's tiles.")
    srcset: str = Field(default="", description="Every WebP size, for an `img`'s `srcset`.")
    width: int
    height: int
    original_name: str
    alt: str
    alt_confirmed: bool = Field(description="False while the alt text is the file's name.")
    credit: str | None = None
    taken_on: date | None = None
    source: MediaSource
    created_at: datetime
    event_id: int | None = None
    series_id: int | None = None
    context: str | None = Field(default=None, description="The event's title or the series' name.")


class PostRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str


class MediaDetail(MediaOut):
    used_in: list[PostRef] = Field(description="The posts that show it — counted, not stored.")


class ImportedOut(MediaOut):
    created: bool = Field(description="False: the picture was in the library already.")


class MediaFields(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    alt: str | None = Field(default=None, max_length=300)
    credit: str | None = Field(default=None, max_length=160)
    event_id: int | None = Field(default=None, description="Sent: the picture is this event's.")
    series_id: int | None = Field(default=None, description="Sent: the picture is this series'.")

    @field_validator("credit")
    @classmethod
    def _none_if_empty(cls, value: str | None) -> str | None:
        return value or None


class MediaBulkFields(BaseModel):
    """One change for several pictures — a regatta's batch at once (Story R-2)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    ids: list[int] = Field(min_length=1, max_length=500)
    credit: str | None = Field(default=None, max_length=160)
    event_id: int | None = Field(default=None, description="Sent: they are this event's.")
    series_id: int | None = Field(default=None, description="Sent: they are this series'.")

    @field_validator("credit")
    @classmethod
    def _none_if_empty(cls, value: str | None) -> str | None:
        return value or None


class MediaIds(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)


class Updated(BaseModel):
    updated: int


class KeptPicture(BaseModel):
    id: int
    used_in: list[PostRef]


class MediaDeleted(BaseModel):
    deleted: list[int]
    kept: list[KeptPicture] = Field(description="Pictures a post still shows, not deleted.")


class PublicPicture(BaseModel):
    """A picture on a league's media page (Story R-3)."""

    id: int
    url: str
    thumb_url: str
    srcset: str
    width: int
    height: int
    alt: str
    credit: str | None = None
    taken_on: date | None = None
    event_id: int | None = None
    series_id: int | None = None
    context: str | None = Field(default=None, description="The event's title or the series' name.")


class ImportKeyOut(BaseModel):
    id: int
    label: str
    prefix: str = Field(description="The key's first characters, to tell keys apart.")
    credit: str | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime
    event_id: int | None = None
    series_id: int | None = None
    context: str | None = None
    active: bool
    pictures: int = Field(description="How many pictures arrived with it.")
    last_used_at: datetime | None = None


class ImportKeyCreated(ImportKeyOut):
    key: str = Field(description="The key itself — answered this once, never again.")


class ImportKeyCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    label: str = Field(min_length=3, max_length=120)
    credit: str | None = Field(default=None, max_length=160)
    valid_days: int | None = Field(
        default=30, ge=1, le=366, description="How long it works; empty: until revoked."
    )
    event_id: int | None = Field(default=None, description="Its pictures are this event's.")
    series_id: int | None = Field(default=None, description="Its pictures are this series'.")


class FromUrl(BaseModel):
    url: str = Field(min_length=8, max_length=2000)


class ImportKeyInfo(BaseModel):
    """What a source may know about its own key — for the upload page's greeting."""

    label: str
    credit: str | None = None
    expires_at: datetime | None = None
    context: str | None = Field(default=None, description="What the pictures are for.")


# ---------------------------------------------------------------- editorial: the library


@admin_router.get("/media", response_model=Page[MediaOut], summary="The picture library")
async def list_media(
    q: str | None = Query(default=None, description="Search in name, alt text and credit"),
    event_id: int | None = Query(default=None, description="An event's pictures"),
    series_id: int | None = Query(
        default=None, description="A series' pictures — its own and its events'"
    ),
    alt_missing: bool = Query(default=False, description="Only those whose alt text is a name"),
    params: PageParams = PageInput,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_editor),
) -> Page[MediaOut]:
    """Newest first."""
    stmt = media.in_context(
        apply_search(_with_context(), q, MediaItem.original_name, MediaItem.alt, MediaItem.credit),
        event_id,
        series_id,
    )
    if alt_missing:
        stmt = stmt.where(MediaItem.alt_confirmed.is_(False))
    items, total = await paginate(
        session,
        stmt,
        params,
        sortable={"created_at": MediaItem.created_at},
        default_order=[MediaItem.created_at.desc(), MediaItem.id.desc()],
    )
    return page_of([_out(item) for item in items], total, params)


@admin_router.post(
    "/media", response_model=ImportedOut, summary="Upload a picture into the library"
)
async def upload_media(
    response: Response,
    file: UploadFile = File(...),
    alt: str | None = Form(default=None, max_length=300),
    credit: str | None = Form(default=None, max_length=160),
    event_id: int | None = Form(default=None, description="The picture is this event's."),
    series_id: int | None = Form(default=None, description="The picture is this series'."),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_editor),
) -> ImportedOut:
    """A JPEG, PNG or WebP — told by its content, not its name — re-encoded. 201 for a new
    entry, 200 with the entry it already is for a picture the library holds (which keeps
    its own alt text, credit and context)."""
    await media.check_context(session, event_id, series_id)
    stored = await media.store(
        session,
        await file.read(),
        original_name=file.filename or "",
        arrival=media.Arrival(user_id=user.id, event_id=event_id, series_id=series_id),
        alt=(alt or "").strip() or None,
        credit=(credit or "").strip() or None,
    )
    return await _imported(session, response, stored)


@admin_router.post(
    "/media/from-url", response_model=ImportedOut, summary="Fetch a picture from a web address"
)
async def fetch_media(
    response: Response,
    body: FromUrl,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_editor),
) -> ImportedOut:
    """Copied into the library, never linked: a picture on someone else's server can vanish
    or change. Public addresses only (``media-url-invalid``); ``media-url-unreachable`` when
    it cannot be fetched; refused like an upload when it is not a picture."""
    fetched = await media.fetch(body.url)
    stored = await media.store(
        session, fetched.raw, original_name=fetched.name, arrival=media.Arrival(user_id=user.id)
    )
    return await _imported(session, response, stored)


@admin_router.get(
    "/media/named/{name}", response_model=MediaDetail, summary="One picture, by its file name"
)
async def get_media_by_name(
    name: str,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_editor),
) -> MediaDetail:
    """The entry behind an address in a post's text — the editor knows a picture by it."""
    item = await session.scalar(select(MediaItem).where(MediaItem.name == name))
    if item is None:
        raise Problem(404, "media-not-found", "No such picture.")
    return await _detail(session, item)


@admin_router.get("/media/{media_id}", response_model=MediaDetail, summary="One picture")
async def get_media(
    media_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_editor),
) -> MediaDetail:
    return await _detail(session, await get_or_404(session, MediaItem, media_id))


@admin_router.get(
    "/media/{media_id}/original",
    summary="A picture at its full size",
    response_class=Response,
    responses={200: {"content": {"image/jpeg": {}}}},
)
async def download_media_original(
    media_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_editor),
) -> Response:
    """The picture as large as it was uploaded, for the press — re-encoded as a JPEG
    without the camera's metadata, never the stored original, which carries its location."""
    item = await get_or_404(session, MediaItem, media_id)
    data = await asyncio.to_thread(media.original, item)
    if data is None:
        raise Problem(404, "media-not-found", "No such picture.")
    stem = Path(item.original_name).stem or item.name
    return Response(
        data,
        media_type="image/jpeg",
        headers={"Content-Disposition": f'attachment; filename="{_ascii(stem)}.jpg"'},
    )


@admin_router.patch(
    "/media/{media_id}",
    response_model=MediaDetail,
    summary="Correct a picture's alt text or credit",
)
async def update_media(
    media_id: int,
    body: MediaFields,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_editor),
) -> MediaDetail:
    item = await get_or_404(session, MediaItem, media_id)
    changes = body.model_dump(exclude_unset=True)
    if "event_id" in changes or "series_id" in changes:
        # One of them is the picture's context; sending one replaces the other.
        event_id, series_id = changes.pop("event_id", None), changes.pop("series_id", None)
        await media.check_context(session, event_id, series_id)
        item.event_id, item.series_id = event_id, series_id
    if "alt" in changes:
        item.alt_confirmed = bool(changes["alt"])
    for name, value in changes.items():
        setattr(item, name, value if name == "credit" else (value or ""))
    await session.commit()
    return await _detail(session, item)


@admin_router.patch("/media", response_model=Updated, summary="Change several pictures at once")
async def update_many_media(
    body: MediaBulkFields,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_editor),
) -> Updated:
    """One credit, or one event or series, for every picture named — what is not sent
    stays as each picture has it."""
    items = await _many(session, body.ids)
    changes = body.model_dump(exclude_unset=True, exclude={"ids"})
    if "event_id" in changes or "series_id" in changes:
        event_id, series_id = changes.pop("event_id", None), changes.pop("series_id", None)
        await media.check_context(session, event_id, series_id)
        for item in items:
            item.event_id, item.series_id = event_id, series_id
    if "credit" in changes:
        for item in items:
            item.credit = changes["credit"]
    await session.commit()
    return Updated(updated=len(items))


@admin_router.post("/media/delete", response_model=MediaDeleted, summary="Delete several pictures")
async def delete_many_media(
    body: MediaIds,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_editor),
) -> MediaDeleted:
    """Every one no post shows; the others are kept and answered with their posts."""
    done = await media.delete_many(session, await _many(session, body.ids))
    return MediaDeleted(
        deleted=done.deleted,
        kept=[
            KeptPicture(id=item_id, used_in=[PostRef.model_validate(p) for p in posts])
            for item_id, posts in done.kept.items()
        ],
    )


@admin_router.delete(
    "/media/{media_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a picture"
)
async def delete_media(
    media_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_editor),
) -> Response:
    """Refused (409 ``media-in-use``, naming the posts) while a post shows it."""
    await media.delete(session, await get_or_404(session, MediaItem, media_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- editorial: import keys


@admin_router.get("/import-keys", response_model=list[ImportKeyOut], summary="The import keys")
async def list_import_keys(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_editor),
) -> list[ImportKeyOut]:
    """Newest first, revoked ones included — their pictures still say where they came from."""
    keys = list(
        (
            await session.execute(
                select(ImportKey)
                .options(selectinload(ImportKey.event), selectinload(ImportKey.series))
                .order_by(ImportKey.id.desc())
            )
        ).scalars()
    )
    use = await media.key_use(session, [key.id for key in keys])
    return [_key_out(key, use.get(key.id)) for key in keys]


@admin_router.post(
    "/import-keys",
    response_model=ImportKeyCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Make an import key",
)
async def create_import_key(
    body: ImportKeyCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_editor),
) -> ImportKeyCreated:
    """The answer carries the key itself, the only time it is shown."""
    await media.check_context(session, body.event_id, body.series_id)
    made = await media.make_key(
        session,
        label=body.label,
        credit=body.credit or None,
        valid_days=body.valid_days,
        user_id=user.id,
        event_id=body.event_id,
        series_id=body.series_id,
    )
    await session.refresh(made.row, ["event", "series"])
    return ImportKeyCreated(**_key_out(made.row, None).model_dump(), key=made.key)


@admin_router.delete(
    "/import-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Revoke an import key"
)
async def revoke_import_key(
    key_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_editor),
) -> Response:
    """Refused from now on; what arrived with it stays."""
    key = await get_or_404(session, ImportKey, key_id)
    key.revoked_at = key.revoked_at or utcnow()
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- a source, with its key


async def _source_key(
    x_import_key: str | None = Header(default=None, description="The import key"),
    session: AsyncSession = Depends(get_session),
) -> ImportKey:
    return await media.key_for(session, x_import_key)


@import_router.get("/key", response_model=ImportKeyInfo, summary="The key this source holds")
async def get_import_key(
    key: ImportKey = Depends(_source_key), session: AsyncSession = Depends(get_session)
) -> ImportKeyInfo:
    """401 ``import-key-invalid`` for a key that is unknown, revoked or expired."""
    await session.refresh(key, ["event", "series"])
    return ImportKeyInfo(
        label=key.label, credit=key.credit, expires_at=key.expires_at, context=context_of(key)
    )


@import_router.post("/media", response_model=ImportedOut, summary="Deliver a picture")
async def import_media(
    response: Response,
    file: UploadFile = File(...),
    alt: str | None = Form(default=None, max_length=300),
    credit: str | None = Form(default=None, max_length=160),
    external_id: str | None = Form(
        default=None, max_length=200, description="The source's own id: sent twice, one entry."
    ),
    key: ImportKey = Depends(_source_key),
    session: AsyncSession = Depends(get_session),
) -> ImportedOut:
    """The one way a source puts a picture into the library. 201 for a new entry; 200 with
    the existing one for the same bytes, or the same ``external_id`` from this key."""
    stored = await media.store(
        session,
        await file.read(),
        original_name=file.filename or "",
        arrival=media.Arrival(import_key=key, external_id=(external_id or "").strip() or None),
        alt=(alt or "").strip() or None,
        credit=(credit or "").strip() or None,
    )
    return await _imported(session, response, stored)


# ---------------------------------------------------------------- everyone


@public_router.get(
    "", response_model=Page[PublicPicture], summary="A league's photos, for its media page"
)
async def list_league_media(
    league: str | None = Query(
        default=None, description="The league's slug; without it, every league's pictures"
    ),
    params: PageParams = PageInput,
    session: AsyncSession = Depends(get_session),
) -> Page[PublicPicture]:
    """Its published series' pictures and their published events', newest regatta first
    (Story R-3)."""
    stmt = media.public_in_league(league).options(
        selectinload(MediaItem.event), selectinload(MediaItem.series)
    )
    total = await session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = await session.execute(stmt.limit(params.limit).offset(params.offset))
    return page_of([public_picture(item) for item in rows.scalars()], total or 0, params)


@public_router.get("/{file_name}", summary="A picture from the library")
async def get_media_file(file_name: str) -> FileResponse:
    """``<name>.webp`` (the largest) or ``<name>-<edge>.webp`` for an edge of
    ``media.EDGES``; ``<name>.jpg`` and ``<name>-thumb.jpg`` from before WebP still answer.
    The name is random and a file never changes under it, so it is cached for good."""
    path = await asyncio.to_thread(media.file_path, file_name)
    if path is None:
        raise Problem(404, "media-not-found", "No such picture.")
    return FileResponse(
        path,
        media_type="image/webp" if path.suffix == ".webp" else "image/jpeg",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


# ---------------------------------------------------------------- helpers


def _ascii(name: str) -> str:
    """A file name a header can carry — anything else becomes ``_``."""
    return "".join(c if c.isascii() and (c.isalnum() or c in "-_.") else "_" for c in name)[:100]


def _with_context():
    return select(MediaItem).options(selectinload(MediaItem.event), selectinload(MediaItem.series))


def public_picture(item: MediaItem) -> PublicPicture:
    """A picture as the public site shows it — load ``event`` and ``series`` first."""
    return PublicPicture(
        **_out(item).model_dump(include=set(PublicPicture.model_fields) - {"context"}),
        context=context_of(item),
    )


def _out(item: MediaItem) -> MediaOut:
    """Load ``event`` and ``series`` first."""
    return MediaOut.model_validate(item).model_copy(
        update={"context": context_of(item), "srcset": media.srcset(item)}
    )


async def _many(session: AsyncSession, ids: list[int]) -> list[MediaItem]:
    """The pictures named, every one of them — an unknown id is a 404, never skipped."""
    rows = list((await session.execute(select(MediaItem).where(MediaItem.id.in_(ids)))).scalars())
    missing = set(ids) - {item.id for item in rows}
    if missing:
        raise Problem(404, "media-not-found", "No such picture.", ids=sorted(missing))
    return rows


async def _imported(session: AsyncSession, response: Response, stored: media.Stored) -> ImportedOut:
    response.status_code = status.HTTP_201_CREATED if stored.created else status.HTTP_200_OK
    await session.refresh(stored.item, ["event", "series"])
    return ImportedOut(**_out(stored.item).model_dump(), created=stored.created)


async def _detail(session: AsyncSession, item: MediaItem) -> MediaDetail:
    await session.refresh(item, ["event", "series"])
    posts = await media.used_in(session, item)
    return MediaDetail(
        **_out(item).model_dump(),
        used_in=[PostRef.model_validate(post) for post in posts],
    )


def _key_out(key: ImportKey, use: media.KeyUse | None) -> ImportKeyOut:
    now = utcnow()
    expires = key.expires_at
    if expires is not None and expires.tzinfo is None:  # SQLite hands back naive times
        expires = expires.replace(tzinfo=now.tzinfo)
    return ImportKeyOut(
        id=key.id,
        label=key.label,
        prefix=key.prefix,
        credit=key.credit,
        expires_at=key.expires_at,
        revoked_at=key.revoked_at,
        created_at=key.created_at,
        event_id=key.event_id,
        series_id=key.series_id,
        context=context_of(key),
        active=key.revoked_at is None and (expires is None or expires > now),
        pictures=use.pictures if use else 0,
        last_used_at=use.last_used_at if use else None,
    )

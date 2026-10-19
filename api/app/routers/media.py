"""The picture library and its import API — Story R-2, `docs/PLAN_MEDIA.md`.

Three doors, each with its own guard:

* ``/api/admin/media``, ``/api/admin/import-keys`` — editorial (the site's ``editor``,
  and its ``admin`` through the model), like posts (Story R-1);
* ``/api/import`` — a **source**, with an import key in ``X-Import-Key`` and no person
  signed in: our upload page first, later a Nextcloud or Flickr bridge. Every source uses
  these two endpoints and nothing else;
* ``/api/media/<name>.jpg`` — everyone: a picture is stored to be shown, and its random
  name is the only way to it.
"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, File, Form, Header, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_editor
from app.db import get_session
from app.models import ImportKey, MediaItem, MediaSource
from app.models.auth import User
from app.models.base import utcnow
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
    width: int
    height: int
    original_name: str
    alt: str
    credit: str | None = None
    taken_on: date | None = None
    source: MediaSource
    created_at: datetime


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

    @field_validator("credit")
    @classmethod
    def _none_if_empty(cls, value: str | None) -> str | None:
        return value or None


class ImportKeyOut(BaseModel):
    id: int
    label: str
    prefix: str = Field(description="The key's first characters, to tell keys apart.")
    credit: str | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime
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


class ImportKeyInfo(BaseModel):
    """What a source may know about its own key — for the upload page's greeting."""

    label: str
    credit: str | None = None
    expires_at: datetime | None = None


# ---------------------------------------------------------------- editorial: the library


@admin_router.get("/media", response_model=Page[MediaOut], summary="The picture library")
async def list_media(
    q: str | None = Query(default=None, description="Search in name, alt text and credit"),
    params: PageParams = PageInput,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_editor),
) -> Page[MediaOut]:
    """Newest first."""
    stmt = apply_search(
        select(MediaItem), q, MediaItem.original_name, MediaItem.alt, MediaItem.credit
    )
    items, total = await paginate(
        session,
        stmt,
        params,
        sortable={"created_at": MediaItem.created_at},
        default_order=[MediaItem.created_at.desc(), MediaItem.id.desc()],
    )
    return page_of([MediaOut.model_validate(item) for item in items], total, params)


@admin_router.post(
    "/media", response_model=ImportedOut, summary="Upload a picture into the library"
)
async def upload_media(
    response: Response,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_editor),
) -> ImportedOut:
    """A JPEG, PNG or WebP — told by its content, not its name — re-encoded. 201 for a new
    entry, 200 with the entry it already is for a picture the library holds."""
    stored = await media.store(
        session,
        await file.read(),
        original_name=file.filename or "",
        arrival=media.Arrival(user_id=user.id),
    )
    return _imported(response, stored)


@admin_router.get("/media/{media_id}", response_model=MediaDetail, summary="One picture")
async def get_media(
    media_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_editor),
) -> MediaDetail:
    return await _detail(session, await get_or_404(session, MediaItem, media_id))


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
    for name, value in body.model_dump(exclude_unset=True).items():
        setattr(item, name, value if name == "credit" else (value or ""))
    await session.commit()
    return await _detail(session, item)


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
    keys = list((await session.execute(select(ImportKey).order_by(ImportKey.id.desc()))).scalars())
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
    made = await media.make_key(
        session,
        label=body.label,
        credit=body.credit or None,
        valid_days=body.valid_days,
        user_id=user.id,
    )
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
async def get_import_key(key: ImportKey = Depends(_source_key)) -> ImportKeyInfo:
    """401 ``import-key-invalid`` for a key that is unknown, revoked or expired."""
    return ImportKeyInfo(label=key.label, credit=key.credit, expires_at=key.expires_at)


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
    return _imported(response, stored)


# ---------------------------------------------------------------- everyone


@public_router.get("/{file_name}", summary="A picture from the library")
async def get_media_file(file_name: str) -> FileResponse:
    """``<name>.jpg`` or ``<name>-thumb.jpg``. The name is random and a file never changes
    under it, so it is cached for good."""
    path = media.file_path(file_name)
    if path is None:
        raise Problem(404, "media-not-found", "No such picture.")
    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


# ---------------------------------------------------------------- helpers


def _imported(response: Response, stored: media.Stored) -> ImportedOut:
    response.status_code = status.HTTP_201_CREATED if stored.created else status.HTTP_200_OK
    return ImportedOut(**MediaOut.model_validate(stored.item).model_dump(), created=stored.created)


async def _detail(session: AsyncSession, item: MediaItem) -> MediaDetail:
    posts = await media.used_in(session, item)
    return MediaDetail(
        **MediaOut.model_validate(item).model_dump(),
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
        active=key.revoked_at is None and (expires is None or expires > now),
        pictures=use.pictures if use else 0,
        last_used_at=use.last_used_at if use else None,
    )

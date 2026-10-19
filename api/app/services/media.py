"""The picture library — Story R-2, `docs/PLAN_MEDIA.md`.

Every picture the site shows from an upload is a `MediaItem`, whichever way it arrived:
editorial's editor and *Media* tab, or a source with an import key (the upload page,
later a Nextcloud or Flickr bridge). This module is the one way in, so the rules hold for
all of them: re-encoded like every picture (`app/services/pictures.py`), the same bytes
twice are one entry, a source's own id twice is one entry, and a picture a post uses
cannot be deleted.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import NamedTuple

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import ImportKey, MediaItem, MediaSource, Post
from app.models.base import utcnow
from app.problems import Problem
from app.services import pictures, uploads

#: The longest edge kept: enough for a full-width header on a large screen.
MASTER_EDGE = 2400
#: The library's tiles and a gallery's smallest step.
THUMB_EDGE = 480
#: A phone's photo, as it leaves the camera; it is re-encoded far smaller anyway.
MAX_BYTES = 25 * 1024 * 1024
#: The prefix of every import key — so a key pasted into the wrong place is recognisable.
KEY_PREFIX = "sbl_imp_"


class Stored(NamedTuple):
    """What storing a picture answers: the entry, and whether this call made it."""

    item: MediaItem
    created: bool


class NewKey(NamedTuple):
    """A key just made: the row, and the key itself — the only time it exists in clear."""

    row: ImportKey
    key: str


@dataclass(frozen=True)
class Arrival:
    """Who and what brought a picture: a person (editorial) or a source (an import key)."""

    user_id: int | None = None
    import_key: ImportKey | None = None
    external_id: str | None = None


class _Encoded(NamedTuple):
    master: bytes
    thumb: bytes
    width: int
    height: int
    taken_on: date | None


def _directory() -> Path:
    directory = Path(settings.uploads_dir) / "media"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def file_path(file_name: str) -> Path | None:
    """The stored file for `/api/media/<file_name>` — ``<name>.jpg`` or ``<name>-thumb.jpg``
    — or ``None`` for anything else, so the serving endpoint never builds a path from a
    request's own text."""
    if not re.fullmatch(r"[0-9a-f]{32}(-thumb)?\.jpg", file_name):
        return None
    found = _directory() / file_name
    return found if found.is_file() else None


def _encode(raw: bytes) -> _Encoded:
    image = pictures.upright(raw, code="media", edge=MASTER_EDGE)
    master = pictures.bounded(image, MASTER_EDGE)
    width, height = master.size
    thumb = pictures.bounded(master.copy(), THUMB_EDGE)
    return _Encoded(
        pictures.jpeg(master), pictures.jpeg(thumb), width, height, pictures.taken_on(raw)
    )


def _alt_from(original_name: str) -> str:
    """A first alt text from the file's name — `kiel_start-race-3.jpg` → "kiel start race
    3". Better than nothing for a screen reader, and flagged in the library as such."""
    stem = Path(original_name).stem
    return re.sub(r"[\s_\-.]+", " ", stem).strip()[:300]


async def store(
    session: AsyncSession,
    raw: bytes,
    content_type: str | None,
    *,
    original_name: str,
    arrival: Arrival,
    alt: str | None = None,
    credit: str | None = None,
) -> Stored:
    """Puts a picture into the library — or answers the entry it already is."""
    await uploads.validated(
        raw,
        content_type,
        code="media",
        what="The picture",
        accept=uploads.IMAGE_TYPES,
        max_bytes=MAX_BYTES,
        by_content=True,
    )
    key = arrival.import_key
    if key is not None and arrival.external_id:
        again = await session.scalar(
            select(MediaItem).where(
                MediaItem.import_key_id == key.id, MediaItem.external_id == arrival.external_id
            )
        )
        if again is not None:
            return Stored(again, created=False)
    digest = hashlib.sha256(raw).hexdigest()
    same = await session.scalar(select(MediaItem).where(MediaItem.sha256 == digest))
    if same is not None:
        return Stored(same, created=False)

    encoded = await asyncio.to_thread(_encode, raw)
    name = uuid.uuid4().hex
    directory = _directory()
    (directory / f"{name}.jpg").write_bytes(encoded.master)
    (directory / f"{name}-thumb.jpg").write_bytes(encoded.thumb)
    item = MediaItem(
        name=name,
        source=MediaSource.IMPORT if key is not None else MediaSource.UPLOAD,
        sha256=digest,
        original_name=original_name[:255],
        alt=(alt or _alt_from(original_name)).strip()[:300],
        credit=(credit or (key.credit if key else None) or None),
        width=encoded.width,
        height=encoded.height,
        taken_on=encoded.taken_on,
        import_key_id=key.id if key else None,
        external_id=arrival.external_id if key else None,
        uploaded_by_user_id=arrival.user_id,
    )
    session.add(item)
    await session.commit()
    return Stored(item, created=True)


async def used_in(session: AsyncSession, item: MediaItem) -> list[Post]:
    """The posts that show the picture — as their own picture or in their text. Asked of
    the posts on every look, never stored: a deleted post frees its pictures by itself."""
    stmt = select(Post).where(
        or_(
            Post.photo_url.in_([item.url, item.thumb_url]),
            Post.body.contains(f"/api/media/{item.name}"),
        )
    )
    return list((await session.execute(stmt.order_by(Post.published_on.desc()))).scalars())


async def delete(session: AsyncSession, item: MediaItem) -> None:
    """Refused while a post shows it, naming those posts — a deleted file would leave a
    broken picture on a published page."""
    posts = await used_in(session, item)
    if posts:
        raise Problem(
            409,
            "media-in-use",
            "A post still shows this picture.",
            posts=[{"id": post.id, "title": post.title} for post in posts],
        )
    for file_name in (f"{item.name}.jpg", f"{item.name}-thumb.jpg"):
        (_directory() / file_name).unlink(missing_ok=True)
    await session.delete(item)
    await session.commit()


# ---------------------------------------------------------------- import keys


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


async def make_key(
    session: AsyncSession,
    *,
    label: str,
    credit: str | None,
    valid_days: int | None,
    user_id: int,
) -> NewKey:
    """A new key, valid for ``valid_days`` (``None``: until revoked). Only its hash is
    kept; the key itself is answered this once."""
    key = KEY_PREFIX + secrets.token_urlsafe(24)
    row = ImportKey(
        label=label,
        key_hash=_hash(key),
        prefix=key[: len(KEY_PREFIX) + 4],
        credit=credit,
        expires_at=utcnow() + timedelta(days=valid_days) if valid_days else None,
        created_by_user_id=user_id,
    )
    session.add(row)
    await session.commit()
    return NewKey(row, key)


async def key_for(session: AsyncSession, key: str | None) -> ImportKey:
    """The key a source presents — refused alike when unknown, revoked or expired, so a
    refusal says nothing about which keys exist."""
    row = (
        await session.scalar(
            select(ImportKey).where(
                ImportKey.key_hash == _hash(key),
                ImportKey.revoked_at.is_(None),
                or_(ImportKey.expires_at.is_(None), ImportKey.expires_at > utcnow()),
            )
        )
        if key
        else None
    )
    if row is None:
        raise Problem(401, "import-key-invalid", "This upload link is not valid (any more).")
    return row


class KeyUse(NamedTuple):
    """How much a key delivered and when last — counted from the pictures."""

    pictures: int
    last_used_at: datetime | None


async def key_use(session: AsyncSession, key_ids: list[int]) -> dict[int, KeyUse]:
    rows = await session.execute(
        select(MediaItem.import_key_id, func.count(), func.max(MediaItem.created_at))
        .where(MediaItem.import_key_id.in_(key_ids))
        .group_by(MediaItem.import_key_id)
    )
    return {key_id: KeyUse(count, last) for key_id, count, last in rows.all()}

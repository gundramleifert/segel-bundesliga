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
import ipaddress
import re
import secrets
import socket
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urljoin, urlsplit

import httpx
from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Event, ImportKey, MediaItem, MediaSource, Post, Series
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
    """Who and what brought a picture: a person (editorial) or a source (an import key) —
    and what it is of, which a key carries for its source and editorial says itself."""

    user_id: int | None = None
    import_key: ImportKey | None = None
    external_id: str | None = None
    event_id: int | None = None
    series_id: int | None = None


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
    *,
    original_name: str,
    arrival: Arrival,
    alt: str | None = None,
    credit: str | None = None,
) -> Stored:
    """Puts a picture into the library — or answers the entry it already is."""
    await uploads.validated(
        raw,
        code="media",
        what="The picture",
        accept=uploads.IMAGE_TYPES,
        max_bytes=MAX_BYTES,
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
    files = (directory / f"{name}.jpg", directory / f"{name}-thumb.jpg")
    files[0].write_bytes(encoded.master)
    files[1].write_bytes(encoded.thumb)
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
        event_id=key.event_id if key else arrival.event_id,
        series_id=key.series_id if key else arrival.series_id,
        external_id=arrival.external_id if key else None,
        uploaded_by_user_id=arrival.user_id,
    )
    session.add(item)
    try:
        await session.commit()
    except Exception as error:
        # Nothing stored, so nothing on disk either. The same bytes arriving twice at once
        # both pass the look-up above; the one that commits second is answered the entry
        # the first one made, as if it had come a moment later.
        await session.rollback()
        for path in files:
            path.unlink(missing_ok=True)
        if isinstance(error, IntegrityError):
            same = await session.scalar(select(MediaItem).where(MediaItem.sha256 == digest))
            if same is not None:
                return Stored(same, created=False)
        raise
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


# ---------------------------------------------------------------- event or series


async def check_context(session: AsyncSession, event_id: int | None, series_id: int | None) -> None:
    """An event or a series, never both — and one that exists."""
    if event_id is not None and series_id is not None:
        raise Problem(
            422, "media-context-both", "A picture belongs to an event or to a series, not both."
        )
    if event_id is not None and await session.get(Event, event_id) is None:
        raise Problem(404, "event-not-found", "No such event.", event_id=event_id)
    if series_id is not None and await session.get(Series, series_id) is None:
        raise Problem(404, "series-not-found", "No such series.", series_id=series_id)


def in_context(stmt: Select, event_id: int | None, series_id: int | None) -> Select:
    """The pictures of an event, or of a series — its own and its events'."""
    if event_id is not None:
        stmt = stmt.where(MediaItem.event_id == event_id)
    if series_id is not None:
        events = select(Event.id).where(Event.series_id == series_id)
        stmt = stmt.where(or_(MediaItem.series_id == series_id, MediaItem.event_id.in_(events)))
    return stmt


# ---------------------------------------------------------------- from a web address

#: Long enough for a slow press server, short enough not to hold a request open.
_FETCH_SECONDS = 15
_REDIRECTS = 3
#: Swapped in tests for an `httpx.MockTransport`: no test calls a live server.
_transport: httpx.AsyncBaseTransport | None = None


class Fetched(NamedTuple):
    raw: bytes
    name: str


async def _public(host: str) -> bool:
    """Whether every address the name resolves to is on the public internet — so a web
    address cannot make the server fetch from itself or its network (SSRF). The name is
    resolved again when httpx connects; a host that answers differently the second time
    (DNS rebinding) is the remaining gap, acceptable for an endpoint only editorial can
    reach."""
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except OSError:
        return False
    return bool(infos) and all(ipaddress.ip_address(info[4][0]).is_global for info in infos)


async def fetch(url: str) -> Fetched:
    """The picture at a web address, copied rather than linked (Story R-2): http or https,
    a public host — checked again on every redirect — at most `MAX_BYTES`, within
    `_FETCH_SECONDS`. Whether it *is* a picture is `store`'s question, by its content."""
    current = url.strip()
    async with httpx.AsyncClient(
        transport=_transport, timeout=_FETCH_SECONDS, follow_redirects=False
    ) as client:
        for _ in range(_REDIRECTS + 1):
            parts = urlsplit(current)
            if parts.scheme not in ("http", "https") or not parts.hostname:
                raise Problem(422, "media-url-invalid", "That is not a web address.")
            if not await _public(parts.hostname):
                raise Problem(422, "media-url-invalid", "That address is not on the internet.")
            try:
                async with client.stream("GET", current) as answer:
                    if answer.is_redirect and "location" in answer.headers:
                        current = urljoin(current, answer.headers["location"])
                        continue
                    if answer.status_code != 200:
                        raise Problem(
                            422,
                            "media-url-unreachable",
                            "The picture could not be fetched.",
                            detail=f"The server answered {answer.status_code}.",
                        )
                    raw = bytearray()
                    async for chunk in answer.aiter_bytes():
                        raw += chunk
                        if len(raw) > MAX_BYTES:
                            raise Problem(422, "media-too-large", "The picture is too large.")
            except httpx.HTTPError as error:
                raise Problem(
                    422, "media-url-unreachable", "The picture could not be fetched."
                ) from error
            name = Path(parts.path).name or parts.hostname
            return Fetched(bytes(raw), name)
    raise Problem(422, "media-url-unreachable", "The address redirects too often.")


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
    event_id: int | None = None,
    series_id: int | None = None,
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
        event_id=event_id,
        series_id=series_id,
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

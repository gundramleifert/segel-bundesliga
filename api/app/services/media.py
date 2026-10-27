"""The picture library — Story R-2, `docs/PLAN_MEDIA.md`.

Every picture the site shows from an upload is a `MediaItem`, whichever way it arrived:
editorial's editor and *Media* tab, or a source with an import key (the upload page,
later a Nextcloud or Flickr bridge). This module is the one way in, so the rules hold for
all of them: re-encoded like every picture (`app/services/pictures.py`), the same bytes
twice are one entry, a source's own id twice is one entry, and a picture a post uses
cannot be deleted.

**Files.** The upload itself is kept as it came, in `uploads/media-originals/` — never
served, because it still carries the camera's EXIF, its location included. What the site
serves is made from it: WebP at each of :data:`EDGES` the picture is larger than, plus
its own size up to the largest, as `uploads/media/<name>-<edge>.webp`. Those are a cache:
a missing one is made again from the original on its first request, so a new size or a
better encoder is a change here, never a request to the photographers.
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
from html import escape
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urljoin, urlsplit

import httpx
from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event, ImportKey, MediaItem, MediaSource, Post, Series
from app.models.base import utcnow
from app.problems import Problem
from app.services import pictures, uploads
from app.storage import storage

#: The longer edges served — a phone's column, a desktop's, a wide header, a large
#: screen's full width. The first is also the library's tile.
EDGES = (480, 960, 1600, 2400)
MASTER_EDGE = EDGES[-1]
THUMB_EDGE = EDGES[0]
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
    variants: dict[int, bytes]
    width: int
    height: int
    taken_on: date | None


#: The served variants' prefix in the upload store (`app/storage.py`).
_SERVED = "media"
#: Where uploads are kept as they came — outside the served prefix on purpose.
_ORIGINALS = "media-originals"


def _put_all(keys: list[str], blobs: list[bytes]) -> None:
    for key, data in zip(keys, blobs, strict=True):
        storage().put(key, data)


def edges_of(width: int, height: int) -> list[int]:
    """The variants a picture of this size has: each of :data:`EDGES` it is larger than,
    and its own longer edge — so a small picture is never blown up, and the largest
    variant is the picture as the site shows it."""
    longest = max(width, height)
    return [edge for edge in EDGES if edge < longest] + [min(longest, MASTER_EDGE)]


def variant_size(width: int, height: int, edge: int) -> tuple[int, int]:
    """A variant's width and height — for `srcset`, without opening the file."""
    scale = edge / max(width, height)
    return max(1, round(width * scale)), max(1, round(height * scale))


def _variant_name(name: str, edge: int) -> str:
    return f"{name}-{edge}.webp"


_FILE = re.compile(r"(?P<name>[0-9a-f]{32})(?:-(?P<edge>\d{3,4}|thumb))?\.(?P<ext>webp|jpg)")


class _Wanted(NamedTuple):
    name: str
    edge: int | None  # None: the largest there is


def _parse(file_name: str) -> _Wanted | None:
    """What `/api/media/<file_name>` asks for, or ``None`` for anything else — so a path is
    never built from a request's own text. ``<name>.jpg`` and ``<name>-thumb.jpg`` are the
    addresses of pictures stored before WebP, and still answer."""
    found = _FILE.fullmatch(file_name)
    if found is None:
        return None
    edge = found["edge"]
    if edge is None:
        return _Wanted(found["name"], None)
    if edge == "thumb":
        return _Wanted(found["name"], THUMB_EDGE)
    return _Wanted(found["name"], int(edge)) if found["ext"] == "webp" else None


def _source(name: str) -> str | None:
    """What a variant is made from: the original, or — for a picture stored before
    originals were kept — the 2400 px JPEG it was stored as."""
    for key in storage().keys(f"{_ORIGINALS}/{name}."):
        return key
    legacy = f"{_SERVED}/{name}.jpg"
    return legacy if storage().exists(legacy) else None


def file_key(file_name: str) -> str | None:
    """The stored file to answer `/api/media/<file_name>` with, made from the original if
    it is not there yet — ``None`` when no such picture exists."""
    wanted = _parse(file_name)
    if wanted is None:
        return None
    if wanted.edge is not None and wanted.edge not in EDGES:
        return None
    if wanted.edge is not None:
        key = f"{_SERVED}/{_variant_name(wanted.name, wanted.edge)}"
        if storage().exists(key):
            return key
    source = _source(wanted.name)
    raw = storage().get(source) if source is not None else None
    if raw is None:
        return None
    image = pictures.upright(raw, code="media", edge=MASTER_EDGE)
    edges = edges_of(*image.size)
    # Larger than the picture is: the largest there is, never a blown-up copy.
    edge = edges[-1] if wanted.edge is None else min(wanted.edge, edges[-1])
    key = f"{_SERVED}/{_variant_name(wanted.name, edge)}"
    if not storage().exists(key):
        storage().put(key, pictures.webp(pictures.bounded(image, edge)))
    return key


def _encode(raw: bytes) -> _Encoded:
    image = pictures.upright(raw, code="media", edge=MASTER_EDGE)
    edges = edges_of(*image.size)
    largest = pictures.bounded(image, edges[-1])
    variants = {edge: pictures.webp(pictures.bounded(largest.copy(), edge)) for edge in edges}
    width, height = largest.size
    return _Encoded(variants, width, height, pictures.taken_on(raw))


def original(item: MediaItem) -> bytes | None:
    """The picture at its full size, re-encoded without its metadata — what editorial
    hands to the press. Never the stored original itself: that carries the location."""
    source = _source(item.name)
    raw = storage().get(source) if source is not None else None
    if raw is None:
        return None
    image = pictures.upright(raw, code="media")
    return pictures.jpeg(image)


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
    media_type = await uploads.validated(
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
    files = [f"{_ORIGINALS}/{name}.{uploads.IMAGE_TYPES[media_type]}"]
    files.extend(f"{_SERVED}/{_variant_name(name, edge)}" for edge in encoded.variants)
    await asyncio.to_thread(_put_all, files, [raw, *encoded.variants.values()])
    item = MediaItem(
        name=name,
        source=MediaSource.IMPORT if key is not None else MediaSource.UPLOAD,
        sha256=digest,
        original_name=original_name[:255],
        alt=(alt or _alt_from(original_name)).strip()[:300],
        alt_confirmed=bool(alt and alt.strip()),
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
        for key in files:
            storage().delete(key)
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
            Post.photo_url.contains(f"/api/media/{item.name}"),
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
    for key in [
        *storage().keys(f"{_SERVED}/{item.name}"),
        *storage().keys(f"{_ORIGINALS}/{item.name}."),
    ]:
        storage().delete(key)
    await session.delete(item)
    await session.commit()


# ---------------------------------------------------------------- many at once


class Deleted(NamedTuple):
    """What deleting several pictures did: the ones gone, and the ones posts still use."""

    deleted: list[int]
    kept: dict[int, list[Post]]


async def delete_many(session: AsyncSession, items: list[MediaItem]) -> Deleted:
    """Each picture no post uses — the rest are kept and named with their posts, the same
    guard as deleting one."""
    deleted, kept = [], {}
    for item in items:
        posts = await used_in(session, item)
        if posts:
            kept[item.id] = posts
            continue
        await delete(session, item)
        deleted.append(item.id)
    return Deleted(deleted, kept)


# ---------------------------------------------------------------- the public media page


def public_in_league(league_slug: str | None) -> Select:
    """The pictures a league's media page shows (Story R-3): of its published series, and
    of their published events — newest regatta first. A picture of nothing, or of a draft,
    is on no page. Without a league, every published series' — the home page's pictures."""
    from app.models import League

    public_series = select(Series.id).where(Series.published.is_(True))
    if league_slug is not None:
        leagues = select(League.id).where(League.slug == league_slug)
        public_series = public_series.where(Series.league_id.in_(leagues))
    public_events = select(Event.id).where(
        Event.series_id.in_(public_series), Event.published.is_(True)
    )
    return (
        select(MediaItem)
        .outerjoin(Event, MediaItem.event_id == Event.id)
        .where(or_(MediaItem.event_id.in_(public_events), MediaItem.series_id.in_(public_series)))
        .order_by(
            Event.starts_on.desc().nulls_last(),
            MediaItem.taken_on.desc().nulls_last(),
            MediaItem.id.desc(),
        )
    )


def public_of(event_id: int | None, series_id: int | None) -> Select:
    """The public pictures of one event, or of one series — its own and its events' — for
    a post's gallery (Story R-1): only what is published, newest first by the camera."""
    if event_id is not None:
        events = select(Event.id).where(Event.id == event_id, Event.published.is_(True))
        where = MediaItem.event_id.in_(events)
    elif series_id is not None:
        public_series = select(Series.id).where(Series.id == series_id, Series.published.is_(True))
        events = select(Event.id).where(
            Event.series_id.in_(public_series), Event.published.is_(True)
        )
        where = or_(MediaItem.series_id.in_(public_series), MediaItem.event_id.in_(events))
    else:
        return select(MediaItem).where(False)  # noqa: FBT003 — nothing named, no gallery
    return (
        select(MediaItem)
        .where(where)
        .order_by(MediaItem.taken_on.desc().nulls_last(), MediaItem.id.desc())
    )


# ---------------------------------------------------------------- shown to readers

#: A library picture's address: its name, whatever size or format the address asks for.
_NAME_IN_URL = re.compile(r"/api/media/([0-9a-f]{32})")
_IMG = re.compile(r"<img\b[^>]*>", re.I)
#: The article's text column: the full width on a phone, about 42 rem from a tablet on.
TEXT_SIZES = "(min-width: 48rem) 42rem, 100vw"


def name_in(url: str | None) -> str | None:
    """The library picture an address points at, if it does."""
    found = _NAME_IN_URL.search(url or "")
    return found[1] if found else None


async def by_name(session: AsyncSession, names: set[str]) -> dict[str, MediaItem]:
    if not names:
        return {}
    rows = await session.execute(select(MediaItem).where(MediaItem.name.in_(names)))
    return {item.name: item for item in rows.scalars()}


def srcset(item: MediaItem) -> str:
    """Every size of the picture, for the browser to pick the one the screen needs."""
    return ", ".join(
        f"/api/media/{item.name}-{edge}.webp {variant_size(item.width, item.height, edge)[0]}w"
        for edge in edges_of(item.width, item.height)
    )


async def for_readers(session: AsyncSession, markup: str) -> str:
    """A post's text as the public page shows it (Story R-1): each library picture with
    the library's alt text, its size — so the page does not jump while it loads — its
    WebP sizes, and its credit as a caption. Taken from the library on every read, so a
    corrected credit is corrected in every post; the stored text keeps only the address."""
    items = await by_name(session, {n for n in map(name_in, _IMG.findall(markup)) if n})

    def shown(tag: re.Match[str]) -> str:
        item = items.get(name_in(tag[0]) or "")
        if item is None:
            return tag[0]
        caption = f"<figcaption>{escape(item.credit)}</figcaption>" if item.credit else ""
        return (
            f'<figure class="media-figure"><img src="{item.url}" srcset="{srcset(item)}" '
            f'sizes="{TEXT_SIZES}" width="{item.width}" height="{item.height}" '
            f'alt="{escape(item.alt)}" loading="lazy" decoding="async">{caption}</figure>'
        )

    return _IMG.sub(shown, markup)


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

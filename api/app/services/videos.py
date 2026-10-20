"""Videos on the media pages — Story R-3.

A video is a YouTube link, never a file (`docs/PLAN_MEDIA.md` §6): hosting video is
YouTube's job, and the league's recordings are there already. What is stored is the
video's id and where to start playing, read from whatever address editorial pastes.
"""

from __future__ import annotations

import re
from typing import NamedTuple
from urllib.parse import parse_qs, urlsplit

from sqlalchemy import Select, or_, select

from app.models import Event, League, Series, Video
from app.problems import Problem

_ID = re.compile(r"[A-Za-z0-9_-]{11}")
_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
    "youtu.be",
}
#: `t=90`, `t=90s`, `t=1m30s`, `t=1h2m3s`.
_TIME = re.compile(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s?)?")


class YouTube(NamedTuple):
    id: str
    start: int


def _seconds(value: str) -> int:
    found = _TIME.fullmatch(value)
    if not found or not value:
        return 0
    hours, minutes, seconds = (int(part or 0) for part in found.groups())
    return hours * 3600 + minutes * 60 + seconds


def parse(url: str) -> YouTube:
    """The video an address points at — a watch page, a short link, an embed, a short
    or a live recording; ``video-url-invalid`` for anything else."""
    parts = urlsplit(url.strip() if "://" in url else f"https://{url.strip()}")
    query = parse_qs(parts.query)
    path = [segment for segment in parts.path.split("/") if segment]
    candidate = None
    if parts.hostname in _HOSTS:
        if parts.hostname == "youtu.be":
            candidate = path[0] if path else None
        elif path[:1] == ["watch"]:
            candidate = (query.get("v") or [None])[0]
        elif len(path) >= 2 and path[0] in ("embed", "shorts", "live", "v"):
            candidate = path[1]
    if candidate is None or not _ID.fullmatch(candidate):
        raise Problem(422, "video-url-invalid", "That is not the address of a YouTube video.")
    start = (query.get("t") or query.get("start") or [""])[0]
    return YouTube(candidate, _seconds(start))


def public_in_league(league_slug: str) -> Select:
    """The videos a league's media page shows — the same rule as its pictures
    (`media.public_in_league`): of its published series and their published events."""
    leagues = select(League.id).where(League.slug == league_slug)
    public_series = select(Series.id).where(
        Series.league_id.in_(leagues), Series.published.is_(True)
    )
    public_events = select(Event.id).where(
        Event.series_id.in_(public_series), Event.published.is_(True)
    )
    return (
        select(Video)
        .outerjoin(Event, Video.event_id == Event.id)
        .where(or_(Video.event_id.in_(public_events), Video.series_id.in_(public_series)))
        .order_by(Event.starts_on.desc().nulls_last(), Video.id.desc())
    )

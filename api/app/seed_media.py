"""The pictures the site starts with — Story R-2.

**Only pictures Sven Jürgensen took**, credited as he signs them on Flickr ("Foto: ©
SvenJJJ", decided 2026-11-06) — never a picture of the league's former company (DSBL GmbH,
galleries marked "c-DSBL"), whatever its press release allows: single pictures of the 2026
matchdays in Kiel, Hamburg and the Finale, each under its 1. Liga act, so the act's report
shows them as its gallery and as its cover (`COVERS`); and 24 of his Junioren-Liga album.
A league page without pictures says so; it does not fail.

**In this repository, at 1600 px** (`seed_data/pictures/`, decided 2026-11-06 for the
Render preview, which builds from git and cannot fetch from Flickr — Flickr refuses
scripted downloads): re-encoded from his downloads without their EXIF, about 300 KB each.
A name not there is looked for in `api/.seed-cache/` (git-ignored), then downloaded into
it. Stored through `app.services.media.store` like any upload — the original kept
privately, the WebP sizes made from it — under its event or series. A picture that cannot
be had is reported and left out.

A step of `app.seed_test_setup`, not of `app.seed`: the test suite seeds with `seed()` in
every worker, and fetching and encoding pictures there would be time spent on nothing it
checks.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

import httpx
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Event, MediaItem, Post, Series
from app.problems import Problem
from app.services.media import Arrival, store

SEEDED = Path(__file__).parent / "seed_data" / "pictures"
CACHE = Path(__file__).parent.parent / ".seed-cache" / "pictures"
# A build without a way out (a sandbox, a firewall) must not wait a minute per picture
# before the connection is given up.
TIMEOUT = httpx.Timeout(60, connect=5)
CREDIT = "Foto: © SvenJJJ"


class SeedPicture(NamedTuple):
    """One picture: its series' slug, a file name for the cache, where it is downloaded
    from, and its alt text."""

    series: str
    name: str
    url: str
    alt: str
    # The act it is of — an event's slug — when it is of one act rather than the series.
    event: str | None = None
    # Its league's home page's picture (Story R-3).
    backdrop: bool = False


def _flickr(photo: str) -> str:
    return f"https://www.flickr.com/photos/svenjjj/{photo}/"


def _single(event: str, photo: str, alt: str, *, backdrop: bool = False) -> SeedPicture:
    return SeedPicture(event.rsplit("-act-", 1)[0], photo, _flickr(photo), alt, event, backdrop)


PICTURES: list[SeedPicture] = [
    _single("dsbl-1-2026-act-3", "55384652567", "Start der Segel-Bundesliga vor Kiel, 2026"),
    # Both divisions sailed Kiel; this one is the 2. Liga's home page picture.
    _single(
        "dsbl-2-2026-act-3",
        "55386171492",
        "Gennaker-Kurs vor Kiel, 3. Spieltag 2026",
        backdrop=True,
    ),
    _single(
        "dsbl-1-2026-act-4",
        "55435924375",
        "J/70 der Segel-Bundesliga vor der Hamburger Skyline, 4. Spieltag 2026",
        backdrop=True,
    ),
    _single("dsbl-1-2026-act-4", "55435269046", "Gennaker-Feld auf der Hamburger Außenalster"),
    _single(
        "dsbl-1-2026-act-6",
        "55595071743",
        "Siegerehrung des Finales am Wannsee: der NRV mit der Meisterschale",
    ),
]

# "JuniorenLiga Kiel", album 72177720328565883: the juniors in Kiel in August 2025. The site
# has no 2025 season, so they are the Junioren-Liga's pictures, dated in their alt text
# (decided 2026-11-06). 24 of its originals, spread over the album.
PICTURES += [
    SeedPicture(
        "junioren-2026",
        photo,
        _flickr(photo),
        f"Deutsche Junioren Segel-Liga in Kiel, August 2025 ({number})",
        backdrop=photo == "54740572087",  # the start, many sails: its home page picture
    )
    for number, photo in enumerate(
        """
        54740487032 54740487397 54740572087 54740575017
        54740576652 54740920922 54741412176 54741413096
        54741414251 54741416226 54741557614 54741633983
        54741641379 54741642144 54741644009 54741645279
        54741758906 54741762651 54741768835 54741771665
        54741773350 54741979623 54741981058 54741988319
        """.split(),
        start=1,
    )
]

# The DSL-Pokal has no picture of its own yet; one of the juniors' — teams of the cup too —
# is its home page's, dated in its alt text like the rest (decided 2026-11-06).
CUP_BACKDROP = "54741645279"
PICTURES = [
    picture._replace(series="dsl-pokal-2026", backdrop=True)
    if picture.name == CUP_BACKDROP
    else picture
    for picture in PICTURES
]

#: A report's slug → its cover, a picture's name; the report then belongs to that act.
COVERS: dict[str, str] = {
    "kiel-muehlenberger-sc-und-sc-ville-gewinnen-den-dritten-spieltag": "55384652567",
    "muehlenberger-segel-club-gewinnt-den-3-spieltag-der-1-segel-bundesliga-in-kiel": (
        "55386171492"
    ),
    "hamburg-der-nrv-gewinnt-zu-hause-und-fuehrt-die-tabelle-an": "55435924375",
    "heimsieg-auf-der-alster-norddeutscher-regatta-verein-gewinnt-den-4-spieltag": ("55435269046"),
    "neunter-titel-fuer-den-nrv-und-ein-aufbruchsignal-fuer-die-segel-bundesliga": ("55595071743"),
}


Fetch = Callable[[SeedPicture], bytes | None]


def cached_or_downloaded(picture: SeedPicture) -> bytes | None:
    """The repository's copy, else the cached one, else the download — kept in the cache
    for the next run."""
    seeded = SEEDED / f"{picture.name}.jpg"
    if seeded.exists():
        return seeded.read_bytes()
    path = CACHE / f"{picture.name}.jpg"
    if path.exists():
        return path.read_bytes()
    try:
        response = httpx.get(picture.url, timeout=TIMEOUT, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)
    return response.content


async def seed_media(
    pictures: list[SeedPicture] = PICTURES, fetch: Fetch = cached_or_downloaded
) -> int:
    """Stores the pictures — again on every run, which `store` answers with the entry the
    same bytes already are. Returns how many were new."""
    created = 0
    missing: list[str] = []
    async with SessionLocal() as session:
        series = dict((await session.execute(select(Series.slug, Series.id))).tuples().all())
        events = dict((await session.execute(select(Event.slug, Event.id))).tuples().all())
        stored_as: dict[str, MediaItem] = {}
        for picture in pictures:
            raw = fetch(picture)
            if raw is None:
                missing.append(picture.name)
                continue
            event_id = events.get(picture.event) if picture.event else None
            series_id = None if event_id else series.get(picture.series)
            try:
                stored = await store(
                    session,
                    raw,
                    original_name=f"{picture.name}.jpg",
                    arrival=Arrival(event_id=event_id, series_id=series_id),
                    alt=picture.alt,
                    credit=CREDIT,
                )
            except Problem:
                # Not a picture after all (an error page answered 200, a cut-off download):
                # left out like one that could not be fetched, and not kept for next time.
                await session.rollback()
                (CACHE / f"{picture.name}.jpg").unlink(missing_ok=True)
                missing.append(picture.name)
                continue
            if not stored.created and (stored.item.event_id, stored.item.series_id) != (
                event_id,
                series_id,
            ):
                # The seed re-creates its events and series under new ids; the entry the
                # same bytes already are follows them, or it would be a picture of nothing.
                stored.item.event_id, stored.item.series_id = event_id, series_id
                await session.commit()
            created += stored.created
            if stored.item.backdrop != picture.backdrop:
                stored.item.backdrop = picture.backdrop
                await session.commit()
            stored_as[picture.name] = stored.item
        for post in (await session.execute(select(Post).where(Post.slug.in_(COVERS)))).scalars():
            cover = stored_as.get(COVERS[post.slug])
            if cover is not None:
                post.photo_url, post.photo_credit = cover.url, CREDIT
                post.event_id = cover.event_id
        await session.commit()
    print(
        f"Pictures: {created} new, {len(pictures) - created - len(missing)} already in the "
        f"library" + (f", {len(missing)} not fetched ({', '.join(missing)})" if missing else "")
    )
    return created

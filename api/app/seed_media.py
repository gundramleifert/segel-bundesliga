"""The pictures the site starts with — Story R-2.

**Only pictures Sven Jürgensen took**, credited as he signs them on Flickr ("Foto: ©
SvenJJJ", decided 2026-11-06) — never a picture of the league's former company (DSBL GmbH,
galleries marked "c-DSBL"), whatever its press release allows. The first twelve of his
albums of the 2026 matchdays in Kiel and Hamburg (flickr.com/photos/svenjjj), each under
its 1. Liga act, so the act's report shows them as its gallery and the first as its
cover (`COVERS`). A league page without pictures says so; it does not fail.

**Copied into the library, never into this repository**, which is public
(`docs/site-structure.md`): the list names each picture's address, and the first run
downloads it into `api/.seed-cache/`, which git ignores; later runs read the cache. Stored
through `app.services.media.store` like any upload — the original kept privately, the
WebP sizes made from it — under its event or series. A picture that cannot be fetched (offline,
moved) is reported and left out.

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


def _album(event: str, alt: str, urls: str) -> list[SeedPicture]:
    """One Flickr album's pictures, in the order he put them: the 2048 px size."""
    return [
        SeedPicture(
            event.rsplit("-act-", 1)[0],
            url.rsplit("/", 1)[1].split("_")[0],
            url,
            f"{alt} ({number})",
            event,
        )
        for number, url in enumerate(urls.split(), start=1)
    ]


_FLICKR = "https://live.staticflickr.com/65535/"
PICTURES: list[SeedPicture] = [
    # "Segel-Bundesliga Alster 4.Spieltag", album 72177720334929291.
    *_album(
        "dsbl-1-2026-act-4",
        "J/70 der Segel-Bundesliga auf der Hamburger Außenalster, 4. Spieltag 2026",
        f"""
        {_FLICKR}55433460020_3f74397abd_k.jpg {_FLICKR}55433181428_84ffd16324_k.jpg
        {_FLICKR}55433069601_4f27742778_k.jpg {_FLICKR}55433069476_7bf96290fb_k.jpg
        {_FLICKR}55433069471_e793a54246_k.jpg {_FLICKR}55433240999_a5c048f015_k.jpg
        {_FLICKR}55433240794_61324b1fc1_k.jpg {_FLICKR}55433068911_d335676675_k.jpg
        {_FLICKR}55432098672_aade21c19e_k.jpg {_FLICKR}55433180258_b8e492c869_k.jpg
        {_FLICKR}55432098327_fd78be6458_k.jpg {_FLICKR}55432098257_a6e448213a_k.jpg
        """,
    ),
    # "Segel-Bundesliga 3.Spieltag 2026", album 72177720334630993.
    *_album(
        "dsbl-1-2026-act-3",
        "J/70 der Segel-Bundesliga vor Kiel, 3. Spieltag 2026",
        f"""
        {_FLICKR}55385778989_cacc73f006_k.jpg {_FLICKR}55385587076_171ea56101_k.jpg
        {_FLICKR}55385992685_a746d6b10e_k.jpg {_FLICKR}55385728433_68f0d5b944_k.jpg
        {_FLICKR}55385728373_13eb762215_k.jpg {_FLICKR}55384663452_5c6e1c2592_k.jpg
        {_FLICKR}55384662042_4093bdbae2_k.jpg {_FLICKR}55385584906_af83149635_k.jpg
        {_FLICKR}55385989400_155745ef49_k.jpg {_FLICKR}55385989325_357eabcbfb_k.jpg
        {_FLICKR}55385725523_ff50944049_k.jpg {_FLICKR}55385988260_c7c0440ca8_k.jpg
        """,
    ),
]

#: A report's slug → its cover, a picture's name; the report then belongs to that act.
COVERS: dict[str, str] = {
    "hamburg-der-nrv-gewinnt-zu-hause-und-fuehrt-die-tabelle-an": "55433460020",
    "kiel-muehlenberger-sc-und-sc-ville-gewinnen-den-dritten-spieltag": "55385778989",
}


Fetch = Callable[[SeedPicture], bytes | None]


def cached_or_downloaded(picture: SeedPicture) -> bytes | None:
    """The cached copy, else the download — kept in the cache for the next run."""
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

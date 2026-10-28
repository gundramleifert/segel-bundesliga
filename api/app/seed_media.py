"""The pictures the site starts with — Story R-2.

**Only pictures Sven Jürgensen took**, credited to him as the photographer ("Foto: Sven
Jürgensen", docs/PLAN_SEEDING.md) — never a picture of the league's former company
(DSBL GmbH, galleries marked "c-DSBL"), whatever its press release allows. The list is
empty until a gallery of his own is confirmed: the DSBL press pictures of the 2026 Finale
that stood here were taken out on 2026-10-27, since no credit to him would have been true.
A league page without pictures says so; it does not fail.

**Copied into the library, never into this repository**, which is public
(`docs/site-structure.md`): the list names each picture's address, and the first run
downloads it into `api/.seed-cache/`, which git ignores; later runs read the cache. Stored
through `app.services.media.store` like any upload — the original kept privately, the
WebP sizes made from it — under its series. A picture that cannot be fetched (offline,
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
from app.models import Series
from app.problems import Problem
from app.services.media import Arrival, store

CACHE = Path(__file__).parent.parent / ".seed-cache" / "pictures"
# A build without a way out (a sandbox, a firewall) must not wait a minute per picture
# before the connection is given up.
TIMEOUT = httpx.Timeout(60, connect=5)
CREDIT = "Foto: Sven Jürgensen"


class SeedPicture(NamedTuple):
    """One picture: its series' slug, a file name for the cache, where it is downloaded
    from, and its alt text."""

    series: str
    name: str
    url: str
    alt: str


PICTURES: list[SeedPicture] = []


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
        for picture in pictures:
            raw = fetch(picture)
            if raw is None:
                missing.append(picture.name)
                continue
            series_id = series.get(picture.series)
            try:
                stored = await store(
                    session,
                    raw,
                    original_name=f"{picture.name}.jpg",
                    arrival=Arrival(series_id=series_id),
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
            if not stored.created and stored.item.series_id != series_id:
                # The seed re-creates its series under new ids; the entry the same bytes
                # already are follows them, or it would be a picture of nothing.
                stored.item.series_id = series_id
                await session.commit()
            created += stored.created
    print(
        f"Pictures: {created} new, {len(pictures) - created - len(missing)} already in the "
        f"library" + (f", {len(missing)} not fetched ({', '.join(missing)})" if missing else "")
    )
    return created

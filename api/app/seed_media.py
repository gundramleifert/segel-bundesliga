"""The pictures the site starts with — Story R-2.

The league office's press pictures of the 2026 Finale on the Wannsee, one per club, from
SmugMug (`Deutsche-Segel-Bundesliga/2026/06-Finale-VSaW-…/PRESSE-c-DSBL`, the galleries
`1. LIGA` and `2. LIGA`; listed on 2026-10-23). Sven Jürgensen, the association's press
contact, agreed to their use, and the press release of 2026-09-16 offers them "zur
redaktionellen Nutzung im Zusammenhang mit der Deutschen Segel-Bundesliga", credited
"© DSBL GmbH" — the credit here.

**Copied into the library, never into this repository**, which is public
(`docs/site-structure.md`): the list below names each picture, and the first run downloads
it (SmugMug's 1600 px size, `X3`) into `api/.seed-cache/`, which git ignores; later runs
read the cache. Stored through `app.services.media.store` like any upload — the original
kept privately, the WebP sizes made from it — under the club's series of 2026 (the seed
has no Finale act). A picture that cannot be fetched (offline, moved at SmugMug) is
reported and left out: the site shows no picture there, it does not fail.

A step of `app.seed_test_setup`, not of `app.seed`: the test suite seeds with `seed()` in
every worker, and fetching and encoding 35 pictures there would be time spent on nothing it
checks.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

import httpx
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Club, Series
from app.services.media import Arrival, store

CACHE = Path(__file__).parent.parent / ".seed-cache" / "finale-2026"
CREDIT = "© DSBL GmbH"
GALLERY = (
    "https://photos.smugmug.com/Deutsche-Segel-Bundesliga/2026/06-Finale-VSaW-1510-17102026/"
    "DSBL-CLUBS-c-DSBL/High-Res-ONLY-PRESS"
)


class FinalePicture(NamedTuple):
    """One club's picture: its series' slug, the club's code here, the file's name, and
    the two parts of its SmugMug address."""

    series: str
    club: str
    name: str
    image: str
    key: str

    @property
    def url(self) -> str:
        return f"{GALLERY}/{self.image}/0/{self.key}/X3/{self.name}-X3.jpg"


PICTURES: list[FinalePicture] = [
    FinalePicture(
        "dsbl-1-2026",
        "KYC (SH)",
        "DSC09131",
        "i-K63BXF9",
        "LTLX3RBN4cCN9QvFwMLPQQxbx7BGrgHnkv934vkDB",
    ),
    FinalePicture(
        "dsbl-1-2026", "DYC", "DSC09198", "i-K9v94ZR", "MrMRRc3m5MfTgjhDSpSqKnZr8P5cGHqVmCmBHzFp6"
    ),
    FinalePicture(
        "dsbl-1-2026", "BYCB", "DSC09285", "i-6PT8VjQ", "M5BCbhSkszMKKpLfC4RGnCQGWn3kNK2h2mQLv4Kwb"
    ),
    FinalePicture(
        "dsbl-1-2026", "NRV", "DSC09464", "i-t6fTWQ5", "M93TN7kRtNjjvhP6g6zJS5LxMfSdrrT2jMMzdCrV5"
    ),
    FinalePicture(
        "dsbl-1-2026", "BSC", "DSC09201", "i-MQZwJ8p", "L9jzSgWd2s3k9CvNt9qDpN8KGxQDGRKKq8HZHQfFw"
    ),
    FinalePicture(
        "dsbl-1-2026", "BoYC", "DSC09260", "i-z8cx4Mg", "NGHrD27k7JkWfqhXfvzqVKR64hRxsCwXzpBS9S9J9"
    ),
    FinalePicture(
        "dsbl-1-2026", "JSC", "DSC09229", "i-wBSwwMx", "MW4GfFH2Qhvggts6v9M6PgGfLdcKxX6jNxvFJp66v"
    ),
    FinalePicture(
        "dsbl-1-2026", "BYC", "DSC09256", "i-fjLHgfS", "MbnfP9LvTnRfZnqJb6WdGBCr7VttqzgCwLmzBqkmh"
    ),
    FinalePicture(
        "dsbl-1-2026", "SVW", "DSC09170", "i-Fnf9sPs", "KgNqbtpmkbBxvzXMMhnQHTBv3zFzmzNz7x3ZSsRb6"
    ),
    FinalePicture(
        "dsbl-1-2026", "MSC", "DSC09142", "i-nBnVQT8", "LxkdnrwMrNqPNWvtDpB2rQMcnn3RBr7JTzpLg8w2s"
    ),
    FinalePicture(
        "dsbl-1-2026", "SVI", "DSC09208", "i-Cqs3wvJ", "KWgGCTnDtV7mxZB4LbJd8vV54K8q8DVwvsV6TcrSP"
    ),
    FinalePicture(
        "dsbl-1-2026", "BYCÜ", "DSC09253", "i-HKFJrPC", "NgDSLJ4S5ZcNvmZg9wHCKnKhGDQqw28nQdXTprgWC"
    ),
    FinalePicture(
        "dsbl-1-2026", "KaR", "DSC09203", "i-JfCpZG5", "NVWGgQCSPMWJSbt8Qx29k7M2WVMs72ZNtf6gMZ8b7"
    ),
    FinalePicture(
        "dsbl-1-2026", "PYC", "DSC09146", "i-zxk7zhc", "LjqB9HC6fbmKgcqL9NPD24rbJG6Phg44xHjrP8tM4"
    ),
    FinalePicture(
        "dsbl-1-2026", "MYC", "DSC09507", "i-FcpjWg4", "MjWNBHwGfXnRf59G7p4Xk3hSZLQJvjh885rKWhkLS"
    ),
    FinalePicture(
        "dsbl-1-2026", "WYC", "DSC09401", "i-WTn3z3x", "KNJTDm3BzV2WZBdcDP748mvJjQfNCtvXX7ZtkzX25"
    ),
    FinalePicture(
        "dsbl-1-2026", "EnSFr", "DSC09168", "i-zc3Nz7L", "K68V8svHDMg8bSpkkss8xkWwNHCDwLSP6hbZbKZR4"
    ),
    FinalePicture(
        "dsbl-1-2026", "SMCÜ", "DSC09137", "i-NHbpjqr", "NQ7PQzTTcWNH6pwMKXV7MhSS7MTC7tj3gRZ4V8fHp"
    ),
    FinalePicture(
        "dsbl-2-2026", "LYC", "DSC09245", "i-Mkf5hrH", "LG9FRzGf2cGDLtrDFKnnxNgrxS9GDrPdsWNhbDrZ4"
    ),
    FinalePicture(
        "dsbl-2-2026", "HSC", "DSC09156", "i-zgdbGgQ", "MKmwM96Ftr5x7dJXFQvChJBw5HXPGQRnbzNSMdP6F"
    ),
    FinalePicture(
        "dsbl-2-2026", "ASVW", "DSC09160", "i-LWVWgLQ", "KZhqfNc4w2tDdsJF2nMjSZFN6qtJRxxKMkLd4RpGg"
    ),
    FinalePicture(
        "dsbl-2-2026", "SV03", "DSC09276", "i-XBhwfhd", "KsqF67GTXwSwZmpqccMf7Rb8wnjRpxPCGVPsNHrcP"
    ),
    FinalePicture(
        "dsbl-2-2026", "SCV", "DSC09159", "i-DcpGPNj", "LBcLSN48VHBvwWSk6QMrr8bHQbZ2zCTk4Kc4vNpCD"
    ),
    FinalePicture(
        "dsbl-2-2026", "BUC", "DSC09163", "i-LrjRv7G", "NKcH6WrzMwHWLDnR9N29MhSk9qZbhsn9NHcFmZQK9"
    ),
    FinalePicture(
        "dsbl-2-2026", "ETUF", "DSC09150", "i-CRQcdLR", "KHMx4cCG5XTsvqWkXVscJctdBxRSxjnHHRctcqz8Z"
    ),
    FinalePicture(
        "dsbl-2-2026", "RSN", "DSC09216", "i-TzSSBQv", "KdWrHwk7k5gQc2z54mNBLsN7GgHjKDpXGQDMm6Bzd"
    ),
    FinalePicture(
        "dsbl-2-2026", "SCRh", "DSC09354", "i-VqS6mpg", "Lh9DRNQMwWwQcbWRmQTLQwdPzPJhHWbXV9bhZwpZw"
    ),
    FinalePicture(
        "dsbl-2-2026", "VSaW", "DSC09297", "i-Cmvjf8k", "KQHDqK6LGxdWHqPJQLSTgZ9NFxr2w22pdmjt3djRX"
    ),
    FinalePicture(
        "dsbl-2-2026", "WsW", "DSC09155", "i-hr7tMQB", "M2txKVQFKndgqT7tdfVDrP3X9q4LR4RvzBNMRD854"
    ),
    FinalePicture(
        "dsbl-2-2026", "MRSV", "DSC09157", "i-RXbtPj4", "LG7XG75H7t48Lnf4926NSD6gXTK4FQKpdC38Wjk8j"
    ),
    FinalePicture(
        "dsbl-2-2026", "FYC", "DSC09327", "i-SgGXB2C", "L8MJzhcCWsBWKQJCNTTNzpc668cw82xN6QG9jtnHg"
    ),
    FinalePicture(
        "dsbl-2-2026",
        "KYC (BA)",
        "DSC09243",
        "i-cxZhWWS",
        "LMNzvn3Gc2V7zq3vq5mJLRGKVbJMZMNd9mnPBwvmS",
    ),
    FinalePicture(
        "dsbl-2-2026", "LSV", "DSC09304", "i-DFjcrrS", "KhMPWJMzh2DK7QfJtjS4c8Qf37QtBcBgG4dKKw52Q"
    ),
    FinalePicture(
        "dsbl-2-2026", "SCHM", "DSC09274", "i-7r2Qcnr", "KQfz4RKQ2Vwp6H9SjjqTg4ftcMfqzVNWqFQcQgWNg"
    ),
    FinalePicture(
        "dsbl-2-2026", "DTYC", "DSC09227", "i-NJgJPPW", "KWbR7SPrx9GptW7vcDrF3F5sNQ3skDf59hrFpJDf5"
    ),
]

#: Fetches one picture's bytes, or None when it cannot be had.
Fetch = Callable[[FinalePicture], bytes | None]


def cached_or_downloaded(picture: FinalePicture) -> bytes | None:
    """The cached copy, else SmugMug's — kept in the cache for the next run."""
    path = CACHE / f"{picture.name}.jpg"
    if path.exists():
        return path.read_bytes()
    try:
        response = httpx.get(picture.url, timeout=60, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)
    return response.content


async def seed_media(
    pictures: list[FinalePicture] = PICTURES, fetch: Fetch = cached_or_downloaded
) -> int:
    """Stores the pictures — again on every run, which `store` answers with the entry the
    same bytes already are. Returns how many were new."""
    created = 0
    missing: list[str] = []
    async with SessionLocal() as session:
        series = dict((await session.execute(select(Series.slug, Series.id))).tuples().all())
        clubs = dict((await session.execute(select(Club.short_name, Club.name))).tuples().all())
        for picture in pictures:
            raw = fetch(picture)
            if raw is None:
                missing.append(picture.club)
                continue
            club = clubs.get(picture.club, picture.club)
            stored = await store(
                session,
                raw,
                original_name=f"{picture.name}.jpg",
                arrival=Arrival(series_id=series.get(picture.series)),
                alt=f"{club} beim Finale der Segel-Bundesliga 2026 auf dem Wannsee",
                credit=CREDIT,
            )
            created += stored.created
    print(
        f"Pictures: {created} new, {len(pictures) - created - len(missing)} already in the "
        f"library" + (f", {len(missing)} not fetched ({', '.join(missing)})" if missing else "")
    )
    return created

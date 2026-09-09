"""Common test setup.

Each test run gets a fresh SQLite database with the complete seed: three matchdays,
one finished, one live, one planned. Story tests check against realistic data volumes —
18 teams and 48 races per matchday — rather than hand-crafted minimal cases where
scoring errors would go unnoticed.
"""

import asyncio
import os
import tempfile
from pathlib import Path

import pytest

# Must come at the very top, not in a fixture: app.config builds its settings on
# import, and the engine depends on it. Once any test module imports app.config,
# the database URL is fixed. Production uses Postgres — the test suite deliberately
# runs against SQLite so it works without a running server.
_TEST_DB_DIR = Path(tempfile.mkdtemp(prefix="sbl-tests-"))
os.environ["SBL_DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DB_DIR / 'test.db'}"
os.environ.setdefault("SBL_JWT_SECRET", "testgeheimnis-nur-fuer-die-testsuite")
# Uploads (sailor photos, Story S-2) also get their own throwaway directory — otherwise
# a test run would leave files behind under the real api/uploads/, and SQLite's reused
# ids (see test_login_and_roles.py::make_user) could make one run's leftover photo look
# like it belongs to an unrelated sailor in the next.
os.environ.setdefault("SBL_UPLOADS_DIR", str(_TEST_DB_DIR / "uploads"))


@pytest.fixture(scope="session")
def database_url() -> str:
    return os.environ["SBL_DATABASE_URL"]


@pytest.fixture(scope="session")
async def seeded(database_url: str):
    from alembic.config import Config

    from alembic import command
    from app.db import engine
    from app.seed import seed

    config = Config(str(Path(__file__).parent.parent / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).parent.parent / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    # Deliberately use real migrations instead of create_all: this catches when a migration
    # drifts from the models. Alembic calls asyncio.run internally, so run in a separate
    # thread — can't do that from an active loop.
    await asyncio.to_thread(command.upgrade, config, "head")

    await seed()
    yield
    await engine.dispose()


@pytest.fixture
async def client(seeded):
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client


class Kennungen:
    """Slug -> primary key for seed data.

    Routes address via primary key; in stories a readable slug is much more
    legible than a number. This bridge keeps them separate.
    """

    def __init__(self, clubs: dict[str, int], events: dict[str, int], series: dict[str, int]):
        self._clubs = clubs
        self._events = events
        self._series = series

    def club(self, slug: str) -> int:
        return self._clubs[slug]

    def event(self, slug: str) -> int:
        return self._events[slug]

    def series(self, slug: str) -> int:
        return self._series[slug]


@pytest.fixture
async def ids(seeded) -> Kennungen:
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import Club, Event, Series

    async with SessionLocal() as session:
        return Kennungen(
            clubs={c.slug: c.id for c in (await session.execute(select(Club))).scalars()},
            events={e.slug: e.id for e in (await session.execute(select(Event))).scalars()},
            series={s.slug: s.id for s in (await session.execute(select(Series))).scalars()},
        )

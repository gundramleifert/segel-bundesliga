"""Set up a complete test system on a fresh installation.

    uv run python -m app.seed_test_setup            # Create and populate schema
    uv run python -m app.seed_test_setup --reset    # discard everything first
    uv run python -m app.seed_test_setup --if-empty # migrate; seed only a database without a series

Combines what would otherwise be four steps: run migrations, create seed data
(`app.seed`), create accounts (`app.seed_users`), put the press pictures into the media
library (`app.seed_media`). Designed for an empty database — after
a `git clone`, a database switch, or when you just want to start fresh.

The run is repeatable: `app.seed` clears existing seed data and recreates it,
`app.seed_users` updates existing accounts, `app.seed_media` finds the pictures it stored
before. With `--reset`, additionally drops all
tables and migration state — the hard reset when the schema is confused. With
`--if-empty`, seeds only a database without any series: a deployment's every start
(`deploy/compose/api-init.sh`), where seeding again would throw away what was changed
through the site.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from alembic.config import Config
from sqlalchemy import select, text

from alembic import command
from app.config import settings
from app.db import engine
from app.models import Base, Series
from app.seed import publish_demo, seed
from app.seed_media import seed_media
from app.seed_users import seed_users

ROOT = Path(__file__).resolve().parent.parent


def _alembic_config() -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    return config


async def _drop_all() -> None:
    """Drop all tables and migration state."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        # Without this, Alembic would consider the schema current and apply no migrations.
        await conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    print("All tables dropped.")


async def _migrate() -> None:
    # Alembic calls asyncio.run internally; can't do that from a running loop.
    await asyncio.to_thread(command.upgrade, _alembic_config(), "head")
    print("Schema up to date.")


async def _has_series() -> bool:
    async with engine.connect() as conn:
        return (await conn.execute(select(Series.id).limit(1))).first() is not None


async def seed_test_setup(
    *, reset: bool = False, if_empty: bool = False, publish_demo_series: bool = False
) -> None:
    target = settings.database_url.split("@")[-1]
    print(f"Database: {target}\n")

    if reset:
        await _drop_all()
    await _migrate()
    if if_empty and await _has_series():
        print("Database already has data: migrated, not seeded.")
        return

    print()
    await seed()
    print()
    await seed_users()
    print()
    await seed_media()
    if publish_demo_series:
        await publish_demo()
        print("Demo series published (test stacks only).")

    print(
        "\nDone. Start with:\n"
        "  uv run uvicorn app.main:app --reload\n"
        "\nFor the role switcher in the interface, set SBL_DEV_LOGIN=true."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop all tables and migration state first.",
    )
    parser.add_argument(
        "--if-empty",
        action="store_true",
        help="Seed only a database without any series (a deployment's every start).",
    )
    parser.add_argument(
        "--publish-demo",
        action="store_true",
        help="Publish the invented demo series (the e2e stacks); never on a real site.",
    )
    args = parser.parse_args()

    try:
        asyncio.run(
            seed_test_setup(
                reset=args.reset, if_empty=args.if_empty, publish_demo_series=args.publish_demo
            )
        )
    finally:
        asyncio.run(engine.dispose())


if __name__ == "__main__":
    main()

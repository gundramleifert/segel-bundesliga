"""Set up a complete test system on a fresh installation.

    uv run python -m app.seed_test_setup            # Create and populate schema
    uv run python -m app.seed_test_setup --reset    # discard everything first

Combines what would otherwise be three steps: run migrations, create seed data
(`app.seed`), create accounts (`app.seed_users`). Designed for an empty database — after
a `git clone`, a database switch, or when you just want to start fresh.

The run is repeatable: `app.seed` clears existing seed data and recreates it,
`app.seed_users` updates existing accounts. With `--reset`, additionally drops all
tables and migration state — the hard reset when the schema is confused.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from alembic.config import Config
from sqlalchemy import text

from alembic import command
from app.config import settings
from app.db import engine
from app.models import Base
from app.seed import seed
from app.seed_users import seed_users

WURZEL = Path(__file__).resolve().parent.parent


def _alembic_config() -> Config:
    config = Config(str(WURZEL / "alembic.ini"))
    config.set_main_option("script_location", str(WURZEL / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    return config


async def _verwerfen() -> None:
    """Drop all tables and migration state."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        # Without this, Alembic would consider the schema current and apply no migrations.
        await conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    print("All tables dropped.")


async def _migrieren() -> None:
    # Alembic calls asyncio.run internally; can't do that from a running loop.
    await asyncio.to_thread(command.upgrade, _alembic_config(), "head")
    print("Schema up to date.")


async def seed_test_setup(*, reset: bool = False) -> None:
    ziel = settings.database_url.split("@")[-1]
    print(f"Database: {ziel}\n")

    if reset:
        await _verwerfen()
    await _migrieren()

    print()
    await seed()
    print()
    await seed_users()

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
    args = parser.parse_args()

    try:
        asyncio.run(seed_test_setup(reset=args.reset))
    finally:
        asyncio.run(engine.dispose())


if __name__ == "__main__":
    main()

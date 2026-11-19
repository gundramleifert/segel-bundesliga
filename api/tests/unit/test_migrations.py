"""The migrations build exactly the schema the models describe.

The test database is made by `alembic upgrade head` (tests/conftest.py), never by
`create_all` — so a model changed without a migration would still pass every other test
against a schema that production never gets. This compares the two, as `alembic check`
does.
"""

import hashlib
from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from app.db import engine
from app.models import Base


async def test_the_migrations_match_the_models(seeded):
    def differences(connection):
        context = MigrationContext.configure(
            connection, opts={"compare_type": True, "compare_server_default": False}
        )
        return compare_metadata(context, Base.metadata)

    async with engine.connect() as connection:
        found = await connection.run_sync(differences)

    assert not found, (
        "The models and the migrations differ — add a migration "
        f"(docs/deploy-server.md § Migrations): {found}"
    )


#: The migration deutsche-segelliga.de was installed with (2026-11-19). It is the baseline:
#: never edited or regenerated again — every model change is a new migration on top of it.
BASELINE = "7133017ca682_initial_schema.py"
BASELINE_SHA256 = "68860ba53389cedc0d67a34ebda7a60186fe06b33bdbf1b13609a0223c569cb9"


def test_the_baseline_migration_is_never_changed():
    path = Path(__file__).parents[2] / "alembic" / "versions" / BASELINE
    assert hashlib.sha256(path.read_bytes()).hexdigest() == BASELINE_SHA256, (
        f"{BASELINE} ran in production and is frozen — add a migration on top instead "
        "(docs/deploy-server.md § Migrations)"
    )

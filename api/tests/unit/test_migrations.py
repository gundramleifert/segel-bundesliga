"""The migrations build exactly the schema the models describe.

The test database is made by `alembic upgrade head` (tests/conftest.py), never by
`create_all` — so a model changed without a migration would still pass every other test
against a schema that production never gets. This compares the two, as `alembic check`
does.
"""

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
        "The models and the migrations differ — regenerate the initial migration, or once "
        f"there is a production, add one (CLAUDE.md § Migrations): {found}"
    )

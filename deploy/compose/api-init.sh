#!/bin/sh
# The one-shot `db-setup` service of compose.yaml: migrate, and seed only an empty database.
#
#   api-init            migrate; seed if there is no series yet (the first start)
#   api-init --reset    drop everything, migrate, seed again (compose.sh run --rm db-setup api-init --reset)
#
# Seeding is not run on every start: app.seed clears the seed's rows and recreates them,
# which would throw away whatever was changed through the site since the last start.
set -eu

# The invented demo series stay hidden unless SEED_PUBLISH_DEMO=true (.env): a
# demonstration server may show them, a real site never (docs/PLAN_SEEDING.md).
demo=""
if [ "${SEED_PUBLISH_DEMO:-false}" = "true" ]; then
  demo="--publish-demo"
fi

if [ "${1:-}" = "--reset" ]; then
  exec python -m app.seed_test_setup --reset $demo
fi

alembic upgrade head

if python - <<'EOF'
import asyncio, sys
from sqlalchemy import text
from app.db import engine

async def main() -> int:
    async with engine.connect() as conn:
        count = (await conn.execute(text("SELECT count(*) FROM series"))).scalar_one()
    await engine.dispose()
    return 0 if count == 0 else 1

sys.exit(asyncio.run(main()))
EOF
then
  echo "Empty database: seeding."
  exec python -m app.seed_test_setup $demo
else
  echo "Database already has data: migrated, not seeded."
fi

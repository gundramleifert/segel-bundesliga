# Local development in one command: `tilt up`, then the dashboard at http://localhost:10350.
#
# Two servers that reload themselves (uvicorn --reload, Vite's HMR), the backing services
# of compose.dev.yml in containers (Postgres, SeaweedFS, Mailpit — Docker required), plus
# the chores that go with them as buttons. The e2e suite's throwaway stacks are
# scripts/dev-stack.sh's job, not this file's.

# ---- backing services (compose.dev.yml) -----------------------------------------------

docker_compose('compose.dev.yml')
dc_resource('db', labels=['services'])
dc_resource('storage', labels=['services'])
dc_resource('mail', labels=['services'], links=[link('http://localhost:8025', 'mails')])

# What points the API — and every chore that touches its data — at those containers. The
# credentials are compose.dev.yml's throwaways.
DEV_DATABASE_URL = 'postgresql+asyncpg://sbl:sbl@localhost:5432/sbl'
dev_env = {
    'SBL_DATABASE_URL': DEV_DATABASE_URL,
    'SBL_STORAGE': 's3',
    'SBL_S3_ENDPOINT_URL': 'http://localhost:8333',
    'SBL_S3_BUCKET': 'sbl-uploads',
    'SBL_S3_ACCESS_KEY_ID': 'sbl-dev',
    'SBL_S3_SECRET_ACCESS_KEY': 'sbl-dev-secret',
    'SBL_SMTP_HOST': 'localhost',
    'SBL_SMTP_PORT': '1025',
    'SBL_SMTP_STARTTLS': 'false',
}

# A fresh container is an empty database: migrate, and seed only when it is empty, so a
# restart keeps what was changed through the site (as deploy/compose/api-init.sh does).
# `reset-db` below starts over.
local_resource(
    'db-setup',
    cmd='uv run python -m app.seed_test_setup --if-empty',
    dir='api',
    env=dev_env,
    resource_deps=['db', 'storage'],
    labels=['services'],
)

# ---- servers ------------------------------------------------------------------------

# SAP Sailing is the local one (deploy/sap-local/), never SAP's hosted server, with the six
# league boats boats.sh created there.
sap_boats = {colour: boat['id'] for colour, boat in read_json('deploy/sap-local/boats.json').items()}

local_resource(
    'api',
    serve_cmd='uv run uvicorn app.main:app --reload --port 8000',
    serve_dir='api',
    serve_env=dict(dev_env, **{
        # The role switcher in the UI (bottom right). Development only — see CLAUDE.md.
        'SBL_DEV_LOGIN': 'true',
        # Signing in needs a key; this one is as throwaway as scripts/dev-stack.sh's.
        'SBL_JWT_SECRET': 'tilt-throwaway-not-a-secret',
        'SBL_SAP_BASE_URL': 'http://127.0.0.1:8888/sailingserver/api',
        'SBL_SAP_USER': 'admin',
        'SBL_SAP_PASSWORD': 'admin',
        'SBL_SAP_BOATS': encode_json(sap_boats),
        # A live act on SAP is followed every 5 s here, so `scripts/sap-season.py sail` shows live.
        'SBL_SAP_POLL_SECONDS': '5',
    }),
    resource_deps=['db-setup', 'storage', 'mail'],
    readiness_probe=probe(http_get=http_get_action(port=8000, path='/api/auth/providers')),
    links=[link('http://localhost:8000/docs', 'API docs')],
    labels=['servers'],
)

local_resource(
    'web',
    serve_cmd='pnpm dev',
    serve_dir='web',
    resource_deps=['api'],
    readiness_probe=probe(http_get=http_get_action(port=5173, path='/')),
    links=[link('http://localhost:5173', 'site')],
    labels=['servers'],
)

# ---- the frontend's API client follows the routes -------------------------------------

# Regenerated whenever a route or a schema changes (CLAUDE.md: "generated, never
# written"); a broken frontend build then shows up in `web`'s typecheck, not as a 404.
local_resource(
    'api-client',
    cmd='scripts/gen-api-client.sh && cd web && pnpm typecheck',
    deps=['api/app/routers', 'api/app/schemas'],
    ignore=['**/__pycache__'],
    auto_init=False,
    labels=['chores'],
)

# ---- buttons ----------------------------------------------------------------------------

local_resource(
    'reset-db',
    cmd='uv run python -m app.seed_test_setup --reset',
    dir='api',
    env=dev_env,
    resource_deps=['db', 'storage'],
    trigger_mode=TRIGGER_MODE_MANUAL,
    auto_init=False,
    labels=['chores'],
)

# The backend suite on Postgres — each worker in a database of its own on the dev server
# (tests/conftest.py). `check` still runs it on SQLite until this one is green.
local_resource(
    'pytest-postgres',
    cmd='uv run pytest -q -n auto',
    dir='api',
    env={'SBL_TEST_DATABASE_URL': DEV_DATABASE_URL},
    resource_deps=['db'],
    trigger_mode=TRIGGER_MODE_MANUAL,
    auto_init=False,
    labels=['chores'],
)

local_resource(
    'check',
    cmd='scripts/check.sh',
    trigger_mode=TRIGGER_MODE_MANUAL,
    auto_init=False,
    labels=['chores'],
)

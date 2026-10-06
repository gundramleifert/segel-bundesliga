# Local development in one command: `tilt up`, then the dashboard at http://localhost:10350.
#
# Two servers that reload themselves (uvicorn --reload, Vite's HMR), plus the chores that
# go with them as buttons. Uses the real api/sbl.db — the e2e suite's throwaway stacks are
# scripts/dev-stack.sh's job, not this file's.

# ---- servers ------------------------------------------------------------------------

local_resource(
    'api',
    serve_cmd='uv run uvicorn app.main:app --reload --port 8000',
    serve_dir='api',
    # The role switcher in the UI (bottom right). Development only — see CLAUDE.md.
    serve_env={'SBL_DEV_LOGIN': 'true'},
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

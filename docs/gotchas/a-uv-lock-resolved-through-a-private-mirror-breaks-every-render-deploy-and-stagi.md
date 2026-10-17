# A uv.lock resolved through a private mirror breaks every Render deploy, and staging silently keeps serving the last API that built

**Symptom** — on staging the role switcher (bottom right) was empty: no test accounts,
although the bundle contained the switcher and `GET /api/dev/users` answered 200.

**Cause** — `api/uv.lock` named `https://nexus.planet-ai.de/…` as the registry of all 65
packages (commit `a6e46a2`: a local uv config rewrites the lock to the company mirror on
every `uv lock`). `api/Dockerfile` runs `uv sync --frozen`, which fetches from exactly
those URLs; Render cannot reach the mirror, so every API build failed — and Render kept
the last API that had built. The static site deployed fine, so staging ran a new frontend
against an old backend: the new switcher groups accounts by a `group` field the old
`/api/dev/users` does not send, and filtered every account out. What misled: the
endpoint answered 200 with 369 accounts, so it looked like a frontend bug; the count (the
seed had been cut to 42) was the clue that the backend was old.

**Rule** — the committed lock names public PyPI, never the mirror. `api/pyproject.toml`
declares `[[tool.uv.index]] pypi … default = true`: a project index takes precedence over
the workstation's user-level `~/.config/uv/uv.toml` (which names the mirror and is
rewritten by `pai-workstation`), so a local `uv lock` / `uv sync` keeps the pypi.org URLs.
`api/Dockerfile` then runs a plain `uv sync --frozen`. (The first fix, re-locking inside
the Dockerfile, was dropped on 2026-10-18: the lock in git still named an unreachable
host.) When staging looks wrong, compare what the API answers with what `main` would
answer before debugging the page.

**Evidence** — after the index entry, `uv lock` with the mirror config active: 64
`registry = "https://pypi.org/simple"`, no `nexus` left, no version changed; the full
`api/Dockerfile` built locally and the container answered `GET /api/leagues`.

**Seen** — 2026-10-18

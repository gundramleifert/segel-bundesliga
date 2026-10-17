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

**Rule** — a build server never trusts the lock's URLs: `api/Dockerfile` re-points the
lock at public PyPI (`uv lock --no-config --default-index https://pypi.org/simple`, which
keeps every locked version) before `uv sync --frozen`. Locally the lock may name the
mirror; a gate on the committed lock does not hold, because any local `uv run` rewrites it
again. And when staging looks wrong, compare what the API answers with what `main` would
answer before debugging the page.

**Evidence** — the Dockerfile's two `RUN` lines, tried on the mirror lock of `39daea2` in
a clean folder: 65 packages, the same versions, no `nexus` URL left, `uv sync --frozen`
resolves.

**Seen** — 2026-10-18

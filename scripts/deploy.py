#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["typer>=0.12"]
# ///
"""Deploy deutsche-segelliga.de: a release candidate on staging, then the release on prod.

    scripts/deploy.py status              # what prod and staging run, what staging passed
    scripts/deploy.py staging 1.2.0       # tag v1.2.0-rc.N on main, run it on a copy of prod
    scripts/deploy.py prod                # tag v1.2.0 on the commit staging passed, deploy it
    scripts/deploy.py logs staging api    # the last lines of a service's log

Runs on your machine; the server does the work in deploy/compose/deploy.sh, which refuses
production for anything staging has not passed. docs/deploy-server.md § Our server.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer

HOST = os.environ.get("SBL_DEPLOY_HOST", "sbl@178.104.43.254")
STAGING_DIR = "~/sbl-staging"  # where the server fetches tags and reads deploy.sh from
SITES = {
    "prod": "https://deutsche-segelliga.de",
    "staging": "https://staging.deutsche-segelliga.de",
}
DIRS = {"prod": "~/sbl", "staging": "~/sbl-staging"}
ROOT = Path(__file__).resolve().parent.parent
VERSION = re.compile(r"^v?(\d+\.\d+\.\d+)$")
RC = re.compile(r"^(v\d+\.\d+\.\d+)-rc\.(\d+)$")

app = typer.Typer(help=__doc__.split("\n")[0], no_args_is_help=True, add_completion=False)


def fail(message: str) -> None:
    typer.secho(f"deploy: {message}", fg=typer.colors.RED, err=True)
    raise typer.Exit(1)


def step(message: str) -> None:
    typer.secho(f"\n== {message}", fg=typer.colors.CYAN, bold=True)


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        fail(f"git {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout.strip()


def remote(script: str, *, capture: bool = False) -> str:
    """Run a bash script on the server as `sbl`; its output streams unless captured."""
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", HOST, "bash -s"],
        input=script,
        text=True,
        capture_output=capture,
    )
    if result.returncode:
        detail = f" — {result.stderr.strip()}" if capture else ""
        fail(f"on {HOST}: exit {result.returncode}{detail}")
    return result.stdout.strip() if capture else ""


def server_deploy(*args: str, ref: str) -> None:
    """Run deploy.sh as it is in `ref` — not the copy in a clone it is about to check out."""
    command = " ".join(shlex.quote(a) for a in args)
    remote(
        f"""set -euo pipefail
git -C {STAGING_DIR} fetch -q --tags --force origin
script=$(mktemp); trap 'rm -f "$script"' EXIT
git -C {STAGING_DIR} show {shlex.quote(ref)}:deploy/compose/deploy.sh > "$script"
bash "$script" {command}
"""
    )


def pushed_main() -> str:
    """The commit to tag: HEAD, on main, exactly what origin has."""
    git("fetch", "-q", "--tags", "--force", "origin")
    if git("rev-parse", "--abbrev-ref", "HEAD") != "main":
        fail("not on main")
    head = git("rev-parse", "HEAD")
    if head != git("rev-parse", "origin/main"):
        fail("HEAD is not origin/main — push (or pull) first: a tag names what origin has")
    return head


@app.command()
def status() -> None:
    """What prod and staging run (tag, image, migration) and what staging last passed."""
    server_deploy("status", ref="origin/main")


@app.command()
def staging(
    version: Annotated[str, typer.Argument(help="The release it is a candidate for: 1.2.0.")],
    check: Annotated[bool, typer.Option(help="Run scripts/check.sh first.")] = True,
) -> None:
    """Tag the next vX.Y.Z-rc.N on main and run it on staging, on a fresh copy of prod."""
    match = VERSION.match(version)
    if not match:
        fail(f"a version is X.Y.Z, not {version!r}")
    release = f"v{match[1]}"
    commit = pushed_main()
    if git("tag", "-l", release):
        fail(f"{release} is released already — pick the next version")
    numbers = [int(m[2]) for t in git("tag", "-l", f"{release}-rc.*").split() if (m := RC.match(t))]
    tag = f"{release}-rc.{max(numbers, default=0) + 1}"

    if check:
        step("scripts/check.sh")
        if subprocess.run([str(ROOT / "scripts" / "check.sh")], cwd=ROOT).returncode:
            fail("checks are red — nothing tagged")

    step(f"{tag} on {commit[:7]}")
    git("tag", tag, commit)
    git("push", "-q", "origin", tag)
    step(f"staging: {tag}")
    server_deploy("staging", tag, ref=tag)
    done = f"\nTry it on {SITES['staging']}, then: scripts/deploy.py prod"
    typer.secho(done, fg=typer.colors.GREEN)


@app.command()
def prod(
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Do not ask.")] = False,
) -> None:
    """Release what staging passed: tag vX.Y.Z on its commit and deploy staging's images."""
    git("fetch", "-q", "--tags", "--force", "origin")
    passed = remote("cat ~/staging-passed 2>/dev/null || true", capture=True).split()
    if len(passed) != 3 or not RC.match(passed[0]):
        fail("staging has passed nothing — scripts/deploy.py staging X.Y.Z first")
    rc, commit, revision = passed
    release = RC.match(rc)[1]
    existing = git("tag", "-l", release)
    if existing and git("rev-parse", f"{release}^{{commit}}") != commit:
        fail(f"{release} exists on another commit — stage the next version")

    typer.echo(f"{rc} passed staging: {git('log', '--oneline', '-1', commit)}")
    typer.echo(f"migration {revision}; production becomes {release}")
    if not yes:
        typer.confirm(f"Deploy {release} to {SITES['prod']}?", abort=True)

    if not existing:
        step(f"{release} on {commit[:7]}")
        git("tag", release, commit)
        git("push", "-q", "origin", release)
    step(f"prod: {release}")
    server_deploy("prod", release, ref=release)
    typer.secho(f"\n{SITES['prod']} runs {release}", fg=typer.colors.GREEN)


@app.command()
def logs(
    where: Annotated[str, typer.Argument(help="prod or staging.")],
    service: Annotated[str, typer.Argument(help="api, web, db, storage or db-setup.")] = "api",
    lines: Annotated[int, typer.Option("--lines", "-n")] = 100,
) -> None:
    """The last lines of one service's log."""
    if where not in DIRS:
        fail("prod or staging")
    dir = DIRS[where]
    remote(
        f"cd {dir} && SECRETS=$PWD/deploy/compose/{where}.sops.env "
        f"deploy/compose/compose.sh logs --no-log-prefix --tail {lines} {shlex.quote(service)}"
    )


if __name__ == "__main__":
    sys.exit(app())

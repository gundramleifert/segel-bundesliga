#!/usr/bin/env bash
# Deploys a release on our server, staging first — docs/deploy-server.md § Our server.
#
#   deploy/compose/deploy.sh staging v1.2.0-rc.1  # built, then run on a fresh copy of production
#   deploy/compose/deploy.sh prod v1.2.0          # staging's very images, nothing built anew
#   deploy/compose/deploy.sh status               # what each runs, and what staging passed
#
# Normally started by scripts/deploy.py from your machine, which runs the copy of this file
# from the commit being deployed — never the one in a clone it is about to check out.
#
# A release candidate is a tag on main; the release is a second tag on the same commit.
# Production takes only what staging has run, so every migration is tried on a copy of the
# real data first: a release whose commit staging has not passed, or a staging that no
# longer runs it, is refused. Run on the server as `sbl`, from either clone.
set -euo pipefail

PROD_DIR="${PROD_DIR:-$HOME/sbl}"
STAGING_DIR="${STAGING_DIR:-$HOME/sbl-staging}"
PASSED="${PASSED:-$HOME/staging-passed}" # "<tag> <commit> <revision>" staging last passed
BACKUPS="${BACKUPS:-$HOME/backup}"

say() { printf '\n== %s\n' "$*"; }
die() { printf 'deploy.sh: %s\n' "$*" >&2; exit 1; }

# `docker compose` of one installation, with its own secrets.
stack() {
  local dir; [[ $1 == prod ]] && dir=$PROD_DIR || dir=$STAGING_DIR
  SECRETS="$dir/deploy/compose/$1.sops.env" "$dir/deploy/compose/compose.sh" "${@:2}"
}
sql() { stack "$1" exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -Atc "$0"' "$2"; }
revision() { sql "$1" "select version_num from alembic_version"; }
image() { [[ $1 == prod ]] && echo "segelliga-$2:local" || echo "segelliga-staging-$2:local"; }
built_from() { docker image inspect -f '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$1" 2>/dev/null; }
uploads() { # $1 installation, $2 export|import, $3 directory
  stack "$1" run --rm --no-deps --user "$(id -u):$(id -g)" -v "$3:/copy" api \
    python -m app.storage_copy "$2" /copy
}

# Writes KEY=value into an installation's .env, where `compose up` reads it: the release
# it runs (SBL_VERSION, SBL_COMMIT), shown in the footer and kept for any later `up`.
set_env() { # $1 installation, $2 key, $3 value
  local dir; [[ $1 == prod ]] && dir=$PROD_DIR || dir=$STAGING_DIR
  local file="$dir/deploy/compose/.env"
  if grep -q "^$2=" "$file"; then sed -i "s|^$2=.*|$2=$3|" "$file"; else echo "$2=$3" >> "$file"; fi
}

# Production's database and uploads, into directory $1.
backup() {
  mkdir -p "$1/uploads"
  stack prod exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$1/db.dump"
  uploads prod export "$1/uploads"
  echo "backup: $1 ($(du -sh "$1" | cut -f1))"
}

deploy_staging() {
  local tag=$1
  [[ $tag =~ ^v[0-9]+\.[0-9]+\.[0-9]+-rc\.[0-9]+$ ]] || die "staging takes a release candidate, vX.Y.Z-rc.N — not '$tag'"
  [[ -d $STAGING_DIR/.git ]] || die "no clone at $STAGING_DIR — docs/deploy-server.md § Our server"
  say "staging: $tag"
  git -C "$STAGING_DIR" fetch -q --tags origin
  local commit; commit=$(git -C "$STAGING_DIR" rev-parse --verify -q "$tag^{commit}") || die "no tag $tag on origin"
  git -C "$STAGING_DIR" merge-base --is-ancestor "$commit" origin/main || die "$tag is not on main"
  git -C "$STAGING_DIR" checkout -q --detach "$commit"
  git -C "$STAGING_DIR" log --oneline -1
  rm -f "$PASSED" # whatever passed before is no longer what staging runs
  SBL_COMMIT=$commit stack staging build

  say "staging: a copy of production"
  local copy="$BACKUPS/for-staging"
  rm -rf "$copy"; backup "$copy"
  stack staging stop api web # nothing holds the tables open
  stack staging up -d --wait db storage
  sql staging "drop schema public cascade; create schema public"
  stack staging exec -T db sh -c 'pg_restore --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < "$copy/db.dump"
  uploads staging import "$copy/uploads"
  echo "production at $(revision staging)"

  say "staging: migrate and start"
  set_env staging SBL_VERSION "$tag"; set_env staging SBL_COMMIT "$commit"
  stack staging up -d --wait
  local now; now=$(revision staging)
  local head; head=$(stack staging run --rm --no-deps -T api alembic heads 2>/dev/null | awk 'NR==1{print $1}')
  [[ $now == "$head" ]] || die "staging is at $now, the code's head is $head — compose.sh logs db-setup"
  rm -rf "$copy"
  echo "$tag $commit $now" > "$PASSED"
  say "staging passed $tag at $now — try it on https://staging.deutsche-segelliga.de, then tag ${tag%-rc.*} on the same commit and: deploy/compose/deploy.sh prod ${tag%-rc.*}"
}

deploy_prod() {
  local tag=$1
  [[ $tag =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "production takes a release, vX.Y.Z — not '$tag'"
  [[ -f $PASSED ]] || die "staging has passed nothing — deploy/compose/deploy.sh staging $tag-rc.N first"
  local rc commit version; read -r rc commit version < "$PASSED"
  git -C "$PROD_DIR" fetch -q --tags origin
  local target; target=$(git -C "$PROD_DIR" rev-parse --verify -q "$tag^{commit}") || die "no tag $tag on origin"
  [[ ${rc%-rc.*} == "$tag" && $target == "$commit" ]] \
    || die "$tag is ${target:0:7}, staging passed $rc at ${commit:0:7} — tag $tag on the commit staging passed, or stage a new rc"
  [[ $(git -C "$STAGING_DIR" rev-parse HEAD) == "$commit" && $(revision staging) == "$version" ]] \
    || die "staging no longer runs ${commit:0:7} at $version — deploy staging again"

  say "prod: backup"
  backup "$BACKUPS/$(date +%F-%H%M)"

  say "prod: $tag — staging's images"
  local service
  for service in api web; do
    [[ $(built_from "$(image staging "$service")") == "$commit" ]] \
      || die "staging's $service image is not built from ${commit:0:7} — deploy staging again"
  done
  git -C "$PROD_DIR" checkout -q --detach "$commit"
  git -C "$PROD_DIR" log --oneline -1
  for service in api web; do docker tag "$(image staging "$service")" "$(image prod "$service")"; done
  set_env prod SBL_VERSION "$tag"; set_env prod SBL_COMMIT "$commit"
  stack prod up --no-build -d --wait
  [[ $(revision prod) == "$version" ]] \
    || die "production is at $(revision prod), staging was at $version — compose.sh logs db-setup"
  stack prod ps --format '{{.Service}} {{.Status}}'
  say "production runs $tag at $version"
}

show_status() {
  local name dir
  for name in prod staging; do
    [[ $name == prod ]] && dir=$PROD_DIR || dir=$STAGING_DIR
    printf '%-8s code %-14s image %-8s db %s\n' "$name" \
      "$(git -C "$dir" describe --always 2>/dev/null || echo '?')" \
      "$(built_from "$(image "$name" api)" | cut -c1-7)" \
      "$(revision "$name" 2>/dev/null || echo '?')"
  done
  if [[ -f $PASSED ]]; then echo "staging passed: $(cat "$PASSED")"; else echo "staging passed: nothing"; fi
}

case "${1:-} ${2:-}" in
  "status ") show_status ;;
  "staging "?*) deploy_staging "$2" ;;
  "prod "?*) deploy_prod "$2" ;;
  *) die "usage: deploy.sh staging vX.Y.Z-rc.N | prod vX.Y.Z | status" ;;
esac

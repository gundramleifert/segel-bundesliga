#!/usr/bin/env bash
# `docker compose` for this stack, with the secrets decrypted from secrets.sops.env.
#
#   deploy/compose/compose.sh up --build -d --wait
#   deploy/compose/compose.sh logs -f api
#   SECRETS=deploy/compose/prod.sops.env deploy/compose/compose.sh up -d
#
# sops hands the decrypted values to docker compose as environment variables, which win
# over .env, so nothing decrypted is ever written to disk; .env keeps the settings that are
# not secret. Without sops, or as someone who is not a recipient (.sops.yaml), put the
# secrets in .env instead and call `docker compose -f deploy/compose/compose.yaml` directly.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
secrets="${SECRETS:-$here/secrets.sops.env}"

command -v sops >/dev/null || { echo "compose.sh: sops is not installed — see README.md, \"Secrets\"" >&2; exit 1; }
[[ -f "$secrets" ]] || { echo "compose.sh: no $secrets" >&2; exit 1; }

# sops runs the command through a shell, so the arguments are quoted back into one string.
exec sops exec-env "$secrets" "docker compose -f $(printf '%q' "$here/compose.yaml") $(printf '%q ' "$@")"

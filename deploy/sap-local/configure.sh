#!/usr/bin/env bash
# Lets our local sites embed SAP Sailing's pages (race viewer, leaderboard).
#
#   deploy/sap-local/configure.sh                      # the dev site (5173) and the e2e stacks (5173+n)
#   deploy/sap-local/configure.sh https://other.host   # these origins instead
#
# SAP keeps the allowed origins ("CORS and CSP frame-ancestors" in the admin console's
# Local Server Management) in one MongoDB document and offers no REST call for it — only
# the admin console's GWT-RPC — so this writes that document and restarts the server,
# which reads it on start. Kept until `down -v`.
set -euo pipefail

compose=(docker compose -f "$(cd "$(dirname "$0")" && pwd)/compose.yaml")
origins=("$@")
[[ ${#origins[@]} -gt 0 ]] || origins=(); for p in 5173 5174 5175 5176; do origins+=("http://localhost:$p" "http://127.0.0.1:$p"); done
list=$(printf '"%s",' "${origins[@]}")

# SERVER_NAME in compose.yaml is "test", and so is the database.
"${compose[@]}" exec -T mongo mongosh --quiet test --eval "
db.CORS_FILTER_CONFIGURATIONS.replaceOne(
  {CORS_FILTER_CONFIGURATION_SERVER_NAME: 'test'},
  {CORS_FILTER_CONFIGURATION_SERVER_NAME: 'test', CORS_FILTER_CONFIGURATION_IS_WILDCARD: false,
   CORS_FILTER_CONFIGURATION_ALLOWED_ORIGINS: [${list%,}]},
  {upsert: true})" >/dev/null
"${compose[@]}" restart sailing-analytics >/dev/null 2>&1

for _ in $(seq 1 30); do
  header=$(curl -sI http://127.0.0.1:8888/gwt/RaceBoard.html | grep -i frame-ancestors || true)
  [[ -n $header ]] && { echo "$header"; exit 0; }
  sleep 4
done
echo "configure.sh: SAP Sailing did not come back within two minutes" >&2
exit 1

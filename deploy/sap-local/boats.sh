#!/usr/bin/env bash
# The league's six J/70s on the local SAP Sailing — what SAP's admin console (Boats) does on
# the hosted one, where SAP creates them.
#
#   deploy/sap-local/boats.sh
#
# A league sails six boats that every team takes in turn, but SAP's REST API creates a boat
# only together with a team (`competitors/createandadd`), named after it. So the boats are
# made once, outside the send: written into SAP's MongoDB here, the same document its
# admin console stores, and the server restarted to read them. `boats.json` holds their
# ids by our boat colour (`BOAT_COLORS`); the send (Story VA-15) takes that mapping.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
compose=(docker compose -f "$here/compose.yaml")

docs=$(python3 - "$here/boats.json" <<'PY'
import json, sys
boats = json.load(open(sys.argv[1]))
print(json.dumps([
    {"idtype": "java.util.UUID", "id": b["id"], "name": colour, "sailId": b["sailId"],
     "color": b["color"],
     "boatClass": {"name": "J/70", "typicallyStartsUpwind": True, "hullLengthInMeters": 6.93}}
    for colour, b in boats.items()
]))
PY
)
"${compose[@]}" exec -T mongo mongosh --quiet test --eval "
for (const b of $docs) db.BOATS.replaceOne({id: b.id}, b, {upsert: true})" >/dev/null
"${compose[@]}" restart sailing-analytics >/dev/null 2>&1

first=$(python3 -c "import json,sys; print(next(iter(json.load(open(sys.argv[1])).values()))['id'])" "$here/boats.json")
for _ in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:8888/sailingserver/api/v1/boats/$first" -u admin:admin >/dev/null; then
    echo "six boats on SAP Sailing — ids in deploy/sap-local/boats.json"
    exit 0
  fi
  sleep 4
done
echo "boats.sh: SAP Sailing did not show the boats within two minutes" >&2
exit 1

#!/usr/bin/env bash
# The league's six J/70s on the local SAP Sailing — what SAP's admin console (Boats) does on
# the hosted one, where SAP creates them.
#
#   deploy/sap-local/boats.sh
#
# A league sails six boats that every team takes in turn, so they are made once, outside
# the send, through `POST /v1/boats` with the ids in `boats.json` (by our boat colour,
# `BOAT_COLORS`); the send (Story VA-15) takes that mapping. A boat already there is kept.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
api="${SBL_SAP_DOUBLE:-http://127.0.0.1:8888}/sailingserver/api"
auth=(-u "${SAP_USER:-admin}:${SAP_PASSWORD:-admin}")

python3 - "$here/boats.json" <<'PY' | while read -r id query; do
import json, sys, urllib.parse
for colour, b in json.load(open(sys.argv[1])).items():
    print(b["id"], urllib.parse.urlencode({"boatId": b["id"], "name": colour, "sailid": b["sailId"],
                                           "displayColor": b["color"], "boatclass": "J/70"}))
PY
  if ! curl -sf -o /dev/null "${auth[@]}" "$api/v1/boats/$id"; then
    curl -sf -o /dev/null "${auth[@]}" -X POST "$api/v1/boats?$query"
  fi
done
echo "six boats on SAP Sailing — ids in deploy/sap-local/boats.json"

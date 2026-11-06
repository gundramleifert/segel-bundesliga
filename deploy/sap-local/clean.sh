#!/usr/bin/env bash
# Deletes every event on the local SAP Sailing — with its leaderboard groups, leaderboards
# and regattas — then every regatta left without one, and in SAP's database what REST
# cannot delete: leaderboard groups of no event, the teams ("competitors") and each team's
# own boat, and the race and regatta logs — SAP keeps those by leaderboard name after the
# event is gone, and a new event of the same name would take the old registrations and
# results back. The tests and every "Send to SAP Sailing" leave these behind on every run; the
# six league boats (boats.json) and the server's settings (configure.sh) stay. Restarts
# the server, which reads its store only at start. Only ever against this machine's server.
set -euo pipefail

api="${SBL_SAP_DOUBLE:-http://127.0.0.1:8888}/sailingserver/api"
auth=(-u "${SAP_USER:-admin}:${SAP_PASSWORD:-admin}")

ids() {  # $1 = path, $2 = field — one value per line
  curl -sf "${auth[@]}" "$api/$1" | python3 -c "
import json, sys
for item in json.load(sys.stdin):
    print(item['$2'] if isinstance(item, dict) else item)"
}

quoted() { python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$1"; }

events=0
while read -r id; do
  [ -n "$id" ] || continue
  curl -sf "${auth[@]}" -X DELETE -o /dev/null \
    "$api/v1/events/$id?withLeaderboardGroups=true&withLeaderboards=true&withRegattas=true"
  events=$((events + 1))
done < <(ids "v1/events?showNonPublic=true" id)  # a draft act is a non-public event

regattas=0
while read -r name; do
  [ -n "$name" ] || continue
  curl -sf "${auth[@]}" -X DELETE -o /dev/null "$api/v1/regattas/$(quoted "$name")"
  regattas=$((regattas + 1))
done < <(ids v1/regattas name)

echo "deleted $events events and $regattas regattas left without one"

here="$(cd "$(dirname "$0")" && pwd)"
keep=$(python3 -c "import json, sys; print(json.dumps([b['id'] for b in json.load(open(sys.argv[1])).values()]))" "$here/boats.json")
docker compose -f "$here/compose.yaml" exec -T mongo mongosh --quiet test --eval "
const keep = $keep;
print('removed', db.LEADERBOARD_GROUPS.deleteMany({}).deletedCount, 'groups,',
      db.LEADERBOARD_GROUP_LINKS_FOR_EVENTS.deleteMany({}).deletedCount, 'group links,',
      db.COMPETITORS.deleteMany({}).deletedCount, 'teams,',
      db.BOATS.deleteMany({id: {\$nin: keep}}).deletedCount, 'team boats,',
      db.RACE_LOGS.deleteMany({}).deletedCount, 'race log entries,',
      db.REGATTA_LOGS.deleteMany({}).deletedCount, 'regatta log entries')"
docker compose -f "$here/compose.yaml" restart sailing-analytics >/dev/null 2>&1
until curl -sf -o /dev/null "${api%/sailingserver/api}/gwt/status"; do sleep 3; done
for what in "events?showNonPublic=true" regattas leaderboards leaderboardgroups; do
  echo "  ${what%%\?*} now: $(curl -sf "${auth[@]}" "$api/v1/$what" | python3 -c 'import json, sys; print(len(json.load(sys.stdin)))')"
done
docker compose -f "$here/compose.yaml" exec -T mongo mongosh --quiet test --eval "
print('  teams now: ' + db.COMPETITORS.countDocuments() + ', boats now: ' + db.BOATS.countDocuments())"

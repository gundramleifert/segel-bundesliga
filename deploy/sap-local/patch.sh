#!/usr/bin/env bash
# SAP Sailing with our proposed REST endpoints, before SAP releases them.
#
#   deploy/sap-local/patch.sh [path to a sailing-analytics checkout]   # default: reference/
#   SAP_IMAGE=sap-sailing-analytics:rest-patch docker compose -f deploy/sap-local/compose.yaml up -d
#
# The feature request (`POST /v1/boats`, `POST /v1/leaderboardgroups`,
# `POST /v1/leaderboardgroups/{name}/leaderboards`; results come from SAP's Race Manager app)
# changes a few classes of one module, the REST gateway — the ones in `resources` below. SAP's
# full build (Maven/Tycho, GWT, Android) is hours; the released image ships every module as its
# own jar and has a JDK, so this compiles just those classes against the release's jars and
# swaps them into the gateway jar — a derived image, nothing else changed. Built from the
# checkout's branch `rest-api-6324` (PR #6325); a class the branch changes is one
# more line in `resources`.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
checkout="${1:-$here/../../reference/sailing-analytics}"
api="$checkout/java/com.sap.sailing.server.gateway/src/com/sap/sailing/server/gateway/jaxrs/api"
base="ghcr.io/sap/sailing-analytics:latest-25"
tag="sap-sailing-analytics:rest-patch"

context=$(mktemp -d)
trap 'rm -rf "$context"' EXIT
resources=(
  BoatsResource.java
  LeaderboardGroupsResource.java
)
for resource in "${resources[@]}"; do
  cp "$api/$resource" "$context/"
done
cat > "$context/Dockerfile" <<DOCKERFILE
FROM $base
COPY *.java /tmp/patch/src/
RUN cd /home/sailing/servers/server/plugins \\
 && CP=\$(find "\$PWD" -name '*.jar' | tr '\\n' ':')\$(find "\$PWD" -mindepth 1 -maxdepth 1 -type d | tr '\\n' ':') \\
 && javac -nowarn -proc:none -cp "\$CP" -d /tmp/patch/out /tmp/patch/src/*.java \\
 && jar uf com.sap.sailing.server.gateway_*.jar -C /tmp/patch/out com \\
 && rm -rf /tmp/patch
DOCKERFILE
docker build -q -t "$tag" "$context"
echo "built $tag — start it with: SAP_IMAGE=$tag docker compose -f deploy/sap-local/compose.yaml up -d"

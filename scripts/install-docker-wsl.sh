#!/usr/bin/env bash
# Installs Docker Engine and the Compose plugin in WSL2 (Ubuntu, systemd on) — no Docker
# Desktop — so compose.dev.yml and `tilt up` can run. Run it yourself; it needs sudo:
#
#   scripts/install-docker-wsl.sh
#
# Afterwards restart WSL once (PowerShell: `wsl --shutdown`) so the docker group applies.
# Safe to run again: every step checks or overwrites what it did before.
set -euo pipefail

. /etc/os-release
if [[ "${ID:-}" != "ubuntu" ]]; then
  echo "This script is for Ubuntu; this is ${PRETTY_NAME:-unknown}." >&2
  exit 1
fi
if [[ "$(ps -p 1 -o comm=)" != "systemd" ]]; then
  echo "systemd is not running as PID 1. Put this in /etc/wsl.conf, then 'wsl --shutdown':" >&2
  echo "  [boot]" >&2
  echo "  systemd=true" >&2
  exit 1
fi

echo "==> Docker's apt repository"
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

echo "==> Docker Engine and the Compose plugin"
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo "==> Start it now and on every boot"
sudo systemctl enable --now docker

echo "==> Use it without sudo"
sudo usermod -aG docker "$USER"

echo "==> Check"
sudo docker run --rm hello-world >/dev/null && echo "Docker runs."
docker compose version

cat <<EOF

Done. Restart WSL once so '$USER' is in the docker group without sudo:
  PowerShell:  wsl --shutdown     (then open the terminal again)
Then, in the repository:
  docker compose -f compose.dev.yml up -d      # or simply: tilt up
EOF

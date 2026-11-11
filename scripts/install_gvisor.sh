#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run this script as root inside the Linux VM (for example: sudo bash scripts/install_gvisor.sh)." >&2
  exit 1
fi

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl gnupg
install -d -m 0755 /etc/apt/keyrings
curl -fsSL https://gvisor.dev/archive.key | gpg --dearmor --yes -o /etc/apt/keyrings/gvisor-archive-keyring.gpg
chmod a+r /etc/apt/keyrings/gvisor-archive-keyring.gpg
printf 'deb [arch=%s signed-by=/etc/apt/keyrings/gvisor-archive-keyring.gpg] https://storage.googleapis.com/gvisor/releases release main\n' \
  "$(dpkg --print-architecture)" >/etc/apt/sources.list.d/gvisor.list

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y runsc
runsc --version
runsc install
systemctl reload docker
docker info --format '{{json .Runtimes}}'

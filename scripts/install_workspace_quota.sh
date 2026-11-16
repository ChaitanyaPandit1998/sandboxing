#!/usr/bin/env bash
# Trusted VM operator installation; enrolls a state namespace, never migrates data.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ "$(uname -s)" == Linux ]] || { echo 'Run inside the Linux VM.' >&2; exit 2; }
STATE_DIR="${1:-$HOME/.local/state/gvisor-poc-worker}"
[[ -d "$STATE_DIR" ]] || { echo 'Initialize the worker state first.' >&2; exit 2; }
HELPER=/usr/local/libexec/gvisor-workspace-quota
UNIT=/etc/systemd/system/gvisor-workspace-quota.service
if sudo -n test -e "$HELPER"; then
  sudo -n grep -q 'Root-owned gvisor workspace storage service' "$HELPER" || { echo 'Refusing unrelated helper.' >&2; exit 2; }
fi
if sudo -n test -e "$UNIT"; then
  sudo -n grep -q '^Description=Local gVisor workspace quota mounts$' "$UNIT" || { echo 'Refusing unrelated service.' >&2; exit 2; }
fi
sudo -n install -d -m 700 /var/lib/gvisor-workspace-quota /etc/gvisor-workspace-quota
sudo -n install -d -m 755 /usr/local/libexec
sudo -n install -m 755 "$ROOT/scripts/workspace_quota_service.py" "$HELPER"
sudo -n cmp "$ROOT/scripts/workspace_quota_service.py" "$HELPER"
sudo -n install -m 644 "$ROOT/scripts/workspace_copy.py" /usr/local/libexec/workspace_copy.py
sudo -n cmp "$ROOT/scripts/workspace_copy.py" /usr/local/libexec/workspace_copy.py
sudo -n install -m 644 "$ROOT/deploy/systemd/gvisor-workspace-quota.service" "$UNIT"
sudo -n systemd-analyze verify "$UNIT"
sudo -n "$HELPER" register --state-dir "$STATE_DIR"
sudo -n systemctl daemon-reload
sudo -n systemctl enable --now gvisor-workspace-quota.service
# Changing source followed by another install should verify fresh recovery behavior.
sudo -n systemctl restart gvisor-workspace-quota.service
sudo -n systemctl is-active gvisor-workspace-quota.service

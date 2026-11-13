#!/usr/bin/env bash
# Install in the Linux VM as the existing trusted pilot user; no sudo required.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ "$(uname -s)" == Linux ]] || { echo 'Run inside the Linux VM.' >&2; exit 2; }
[[ "$(loginctl show-user "$(id -un)" -p Linger --value)" == yes ]] || {
  echo 'User lingering is required for cleanup after logout; ask the VM administrator to enable it.' >&2
  exit 2
}
UNIT="$HOME/.config/systemd/user/gvisor-poc-reconciler.service"
if [[ -e "$UNIT" ]] && ! grep -q '^Description=Local gVisor POC worker reconciler$' "$UNIT"; then
  echo 'Refusing to replace an unrelated user service.' >&2; exit 2
fi
mkdir -p "$HOME/gvisor-managed-pilot/scripts" "$HOME/.config/systemd/user" "$HOME/.local/state/gvisor-poc-worker"
chmod 700 "$HOME/.local/state/gvisor-poc-worker"
install -m 644 "$ROOT/scripts/manage_codex_session.py" "$HOME/gvisor-managed-pilot/scripts/"
install -m 644 "$ROOT/scripts/security_history.py" "$HOME/gvisor-managed-pilot/scripts/"
install -m 644 "$ROOT/scripts/console_observability.py" "$HOME/gvisor-managed-pilot/scripts/"
install -m 644 "$ROOT/scripts/run_worker_reconciler.py" "$HOME/gvisor-managed-pilot/scripts/"
install -m 644 "$ROOT/tls_gateway.py" "$HOME/gvisor-managed-pilot/"
install -m 644 "$ROOT/deploy/systemd/gvisor-poc-reconciler.service" "$UNIT"
systemd-analyze --user verify "$UNIT"
systemctl --user daemon-reload
systemctl --user enable --now gvisor-poc-reconciler.service
systemctl --user restart gvisor-poc-reconciler.service
systemctl --user is-active gvisor-poc-reconciler.service

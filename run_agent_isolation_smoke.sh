#!/usr/bin/env bash
set -euo pipefail

IMAGE="${AGENT_IMAGE:-local/agent-session:claude-2.1.322-codex-0.167.1}"
HOST_MARKER="/tmp/agent-session-host-marker-$$"
printf '%s\n' 'synthetic-host-only-marker' > "$HOST_MARKER"
trap 'rm -f "$HOST_MARKER"' EXIT

for runtime in runc runsc; do
  name="agent-isolation-${runtime}-$$"
  echo "=== $runtime ==="
  docker run -d --rm --name "$name" \
    --network=none --runtime="$runtime" \
    --cpus=1 --memory=256m --pids-limit=128 --read-only \
    --tmpfs /tmp:size=64m,uid=10001,gid=10001 \
    --tmpfs /home/agent:size=64m,uid=10001,gid=10001 \
    --tmpfs /workspace:size=256m,uid=10001,gid=10001 \
    --cap-drop=ALL --security-opt=no-new-privileges --user 10001:10001 \
    -e SESSION_MARKER=synthetic-session-a-only \
    "$IMAGE" /bin/bash -c 'printf session-a-only > /workspace/session-a.txt; sleep 45' >/dev/null
  cleanup() { docker rm -f "$name" >/dev/null 2>&1 || true; }
  trap cleanup RETURN

  docker run --rm --network=none --runtime="$runtime" \
    --cpus=1 --memory=256m --pids-limit=128 --read-only \
    --tmpfs /tmp:size=64m,uid=10001,gid=10001 \
    --tmpfs /home/agent:size=64m,uid=10001,gid=10001 \
    --tmpfs /workspace:size=256m,uid=10001,gid=10001 \
    --cap-drop=ALL --security-opt=no-new-privileges --user 10001:10001 \
    "$IMAGE" /bin/bash -c '
      set -eu
      test ! -e /workspace/session-a.txt
      test ! -e /tmp/agent-session-host-marker-'"$$"'
      if grep -aq synthetic-session-a-only /proc/[0-9]*/environ 2>/dev/null; then
        echo cross_session_process_env=UNEXPECTED
        exit 30
      fi
      echo cross_session_file=isolated
      echo cross_session_process_env=not_visible
      echo guest_host_marker=not_visible
    '
  cleanup
  trap - RETURN
  if docker inspect "$name" >/dev/null 2>&1; then
    echo "cleanup=UNEXPECTED container=$name"
    exit 31
  fi
  echo cleanup=complete
done

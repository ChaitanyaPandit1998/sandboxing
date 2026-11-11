#!/usr/bin/env bash
set -euo pipefail

IMAGE="${AGENT_IMAGE:-local/agent-session:claude-2.1.322-codex-0.167.1}"
RUNTIMES=(runc runsc)

run_isolated() {
  local runtime="$1"
  docker run --rm \
    --network=none \
    --runtime="$runtime" \
    --cpus=1 --memory=256m --pids-limit=128 \
    --read-only \
    --tmpfs /tmp:size=64m,uid=10001,gid=10001 \
    --tmpfs /home/agent:size=64m,uid=10001,gid=10001 \
    --tmpfs /workspace:size=256m,uid=10001,gid=10001 \
    --cap-drop=ALL \
    --security-opt=no-new-privileges \
    --user 10001:10001 \
    "$IMAGE" /bin/bash -c '
      set -eu
      test "$(id -u)" = 10001
      grep -E "^(NoNewPrivs|CapEff):" /proc/self/status
      printf probe > /workspace/write-probe
      test -s /workspace/write-probe && echo workspace_write=allowed
      if touch /etc/poc-write-probe 2>/dev/null; then
        echo rootfs_write=UNEXPECTED
        exit 20
      else
        echo rootfs_write=denied
      fi
      node -e "try { process.setuid(0); console.error(\"setuid_root=UNEXPECTED\"); process.exit(21); } catch (e) { if (e.code !== \"EPERM\" && e.code !== \"EACCES\") throw e; console.log(\"setuid_root=denied\"); }"
      node -e "fetch(\"https://1.1.1.1/\").then(() => { console.error(\"direct_egress=UNEXPECTED\"); process.exit(22); }).catch(() => console.log(\"direct_egress=blocked\"));"
    '
}

for runtime in "${RUNTIMES[@]}"; do
  echo "=== $runtime ==="
  run_isolated "$runtime"
done

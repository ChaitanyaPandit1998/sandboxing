#!/usr/bin/env bash
set -euo pipefail

IMAGE="${AGENT_IMAGE:-local/agent-session:claude-2.1.322-codex-0.167.1}"
CLIENT_NET=agent-session-client
EGRESS_NET=agent-session-egress
PROXY=agent-session-proxy
ALLOWED_HOSTS=api.anthropic.com,claude.ai,claude.com,platform.claude.com,auth.openai.com,chatgpt.com

usage() {
  echo "Usage: $0 start <runc|runsc> <claude|codex> | stop | status" >&2
  exit 2
}

start() {
  local runtime="$1" cli="$2" name proxy_ip
  [[ "$runtime" == runc || "$runtime" == runsc ]] || usage
  [[ "$cli" == claude || "$cli" == codex ]] || usage
  name="agent-session-${runtime}-${cli}"

  if docker container inspect "$name" >/dev/null 2>&1; then
    echo "Session container already exists: $name" >&2
    exit 2
  fi
  if ! docker network inspect "$CLIENT_NET" >/dev/null 2>&1; then
    docker network create --internal "$CLIENT_NET" >/dev/null
  fi
  if ! docker network inspect "$EGRESS_NET" >/dev/null 2>&1; then
    docker network create "$EGRESS_NET" >/dev/null
  fi
  if ! docker container inspect "$PROXY" >/dev/null 2>&1; then
    docker run -d --rm --name "$PROXY" --network "$EGRESS_NET" \
      --cpus=1 --memory=128m --pids-limit=64 --read-only --tmpfs /tmp:size=16m \
      --security-opt no-new-privileges --cap-drop=ALL --user 10001:10001 \
      -e "POC_ALLOWED_HOSTS=$ALLOWED_HOSTS" --entrypoint python3 \
      local/gvisor-poc:latest /opt/poc/allowlist_proxy.py >/dev/null
  fi
  if ! docker inspect "$PROXY" --format '{{json .NetworkSettings.Networks}}' | grep -q 'agent-session-client'; then
    docker network connect --alias agent-proxy "$CLIENT_NET" "$PROXY"
  fi
  proxy_ip="$(docker inspect "$PROXY" | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["NetworkSettings"]["Networks"][sys.argv[1]]["IPAddress"])' "$CLIENT_NET")"
  for _ in $(seq 1 20); do
    if docker exec "$PROXY" python3 -c 'import socket; s=socket.create_connection(("127.0.0.1",3128),timeout=1); s.close()' >/dev/null 2>&1; then
      break
    fi
    sleep 0.25
  done

  docker run -d --rm --name "$name" --network "$CLIENT_NET" --runtime="$runtime" \
    --cpus=1 --memory=1g --pids-limit=128 --read-only \
    --tmpfs /tmp:size=128m,uid=10001,gid=10001 \
    --tmpfs /home/agent:size=128m,uid=10001,gid=10001 \
    --tmpfs /workspace:size=512m,uid=10001,gid=10001 \
    --cap-drop=ALL --security-opt=no-new-privileges --user 10001:10001 \
    -e "HTTPS_PROXY=http://${proxy_ip}:3128" -e "HTTP_PROXY=http://${proxy_ip}:3128" \
    -e "https_proxy=http://${proxy_ip}:3128" -e "http_proxy=http://${proxy_ip}:3128" \
    -e NO_PROXY=localhost,127.0.0.1,::1 \
    -e DISABLE_AUTOUPDATER=1 -e DISABLE_UPDATES=1 \
    -e DISABLE_TELEMETRY=1 -e DISABLE_ERROR_REPORTING=1 \
    -e ENABLE_CLAUDEAI_MCP_SERVERS=false -e CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
    "$IMAGE" sleep infinity >/dev/null

  echo "Started $name. Home and workspace are memory-backed; no host files or credentials are mounted."
  echo "Attach from macOS Terminal with: limactl shell gvisor-poc -- docker exec -it $name /bin/bash"
  echo "Inside the container, authenticate with $cli, then make one harmless request on synthetic input."
  echo "Exit and log out when done. Stop all temporary resources with: $0 stop"
}

stop() {
  for name in agent-session-runc-claude agent-session-runsc-claude agent-session-runc-codex agent-session-runsc-codex; do
    docker rm -f "$name" >/dev/null 2>&1 || true
  done
  docker rm -f "$PROXY" >/dev/null 2>&1 || true
  docker network rm "$CLIENT_NET" "$EGRESS_NET" >/dev/null 2>&1 || true
  echo "Stopped the temporary proxy and agent session containers; removed their memory-backed homes."
}

status() {
  docker ps --filter "name=agent-session-" --format '{{.Names}} {{.Status}} {{.Image}}'
  docker network ls --filter "name=agent-session-" --format '{{.Name}} {{.Driver}} {{.Scope}}'
}

case "${1:-}" in
  start)
    [[ $# == 3 ]] || usage
    start "$2" "$3"
    ;;
  stop)
    [[ $# == 1 ]] || usage
    stop
    ;;
  status)
    [[ $# == 1 ]] || usage
    status
    ;;
  *) usage ;;
esac

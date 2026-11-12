#!/usr/bin/env bash
# Run inside the disposable Linux VM. Authentication stays in a tmpfs home.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESSION=poc-codex-tls-session
GATEWAY=poc-codex-tls-gateway
CLIENT_NET=poc-codex-tls-internal
EGRESS_NET=poc-codex-tls-egress
WORK=/tmp/poc-codex-tls-material
LABEL=poc.codex-tls=true

owned() {
  [[ "$(docker inspect "$1" --format '{{index .Config.Labels "poc.codex-tls"}}')" == true ]]
}

stop() {
  for name in "$SESSION" "$GATEWAY"; do
    if docker container inspect "$name" >/dev/null 2>&1; then
      owned "$name" || { echo "Refusing to remove unowned container: $name" >&2; return 1; }
      docker rm -f "$name" >/dev/null
    fi
  done
  for name in "$CLIENT_NET" "$EGRESS_NET"; do
    if docker network inspect "$name" >/dev/null 2>&1; then
      [[ "$(docker network inspect "$name" --format '{{index .Labels "poc.codex-tls"}}')" == true ]] || return 1
      docker network rm "$name" >/dev/null
    fi
  done
  rm -rf "$WORK"
  echo 'Removed the test session, gateway, networks, temporary CA, and memory-backed login home.'
}

start() {
  for name in "$SESSION" "$GATEWAY"; do
    if docker container inspect "$name" >/dev/null 2>&1; then
      echo "Container already exists: $name; use status or stop first" >&2; return 1
    fi
  done
  [[ ! -e "$WORK" ]] || { echo 'Temporary material directory already exists; inspect it first' >&2; return 1; }
  for name in "$CLIENT_NET" "$EGRESS_NET"; do
    ! docker network inspect "$name" >/dev/null 2>&1 || { echo "Network already exists: $name" >&2; return 1; }
  done
  # Roll back this invocation on partial provisioning failure.
  trap 'stop' ERR
  mkdir -m 755 "$WORK"
  cp "$ROOT/tls_gateway.py" "$WORK/addon.py"
  chmod 644 "$WORK/addon.py"
  docker network create --label "$LABEL" --internal "$CLIENT_NET" >/dev/null
  docker network create --label "$LABEL" "$EGRESS_NET" >/dev/null
  docker run -d --name "$GATEWAY" --label "$LABEL" --network "$EGRESS_NET" \
    --user 10001:10001 --read-only --tmpfs /tmp:size=64m,nosuid,nodev \
    --cpus=1 --memory=512m --pids-limit=128 --cap-drop ALL --security-opt no-new-privileges \
    -e POC_ALLOWED_HOSTS=auth.openai.com,chatgpt.com,api.openai.com \
    -v "$WORK/addon.py:/opt/addon.py:ro" --entrypoint mitmdump \
    mitmproxy/mitmproxy:12.3.1@sha256:2711066c855659b5af8b1dbb84494ed3eff69b42ece439c60b4fe09a2db829d4 \
    -q --listen-port 3128 --set confdir=/tmp/ca --set connection_strategy=lazy \
    --set upstream_cert=false --set rawtcp=false --set http2=false \
    --set ssl_insecure=false --set validate_inbound_headers=true -s /opt/addon.py >/dev/null
  docker network connect "$CLIENT_NET" "$GATEWAY"
  for _ in $(seq 1 40); do
    if docker exec "$GATEWAY" cat /tmp/ca/mitmproxy-ca-cert.pem > "$WORK/ca.pem" 2>/dev/null; then break; fi
    sleep 0.25
  done
  test -s "$WORK/ca.pem"
  chmod 644 "$WORK/ca.pem"
  local proxy_ip
  proxy_ip="$(docker inspect "$GATEWAY" --format "{{(index .NetworkSettings.Networks \"$CLIENT_NET\").IPAddress}}")"
  docker run -d --name "$SESSION" --label "$LABEL" --log-driver none \
    --runtime=runsc-stable-20261109 --network "$CLIENT_NET" \
    --cpus=1 --memory=1g --pids-limit=128 --user 10001:10001 --read-only \
    --tmpfs /tmp:size=256m,uid=10001,gid=10001,nosuid,nodev \
    --tmpfs /home/agent:size=512m,uid=10001,gid=10001,nosuid,nodev \
    --tmpfs /workspace:size=512m,uid=10001,gid=10001,nosuid,nodev \
    --cap-drop ALL --security-opt no-new-privileges \
    -v "$WORK/ca.pem:/trust/ca.pem:ro" \
    -e "HTTPS_PROXY=http://$proxy_ip:3128" -e "HTTP_PROXY=http://$proxy_ip:3128" \
    -e "https_proxy=http://$proxy_ip:3128" -e "http_proxy=http://$proxy_ip:3128" \
    -e NO_PROXY=localhost,127.0.0.1,::1 -e CODEX_CA_CERTIFICATE=/trust/ca.pem \
    -e SSL_CERT_FILE=/trust/ca.pem -e NODE_EXTRA_CA_CERTS=/trust/ca.pem \
    -e DISABLE_UPDATES=1 -e DISABLE_AUTOUPDATER=1 \
    local/agent-session:claude-2.1.322-codex-0.167.1 sleep infinity >/dev/null
  docker exec -i "$SESSION" sh -c 'umask 077; mkdir -p "$HOME/.codex"; cat > "$HOME/.codex/config.toml"' <<'TOML'
model_provider = "poc_https"

[model_providers.poc_https]
name = "OpenAI HTTPS through POC gateway"
base_url = "https://chatgpt.com/backend-api/codex"
wire_api = "responses"
requires_openai_auth = true
supports_websockets = false
TOML
  docker exec "$SESSION" sh -c 'test -w /workspace && touch /workspace/preflight && codex --version'
  trap - ERR
  echo 'Ready for private device login in poc-codex-tls-session.'
}

case "${1:-}" in
  start) start ;;
  stop) stop ;;
  status) docker ps -a --filter label="$LABEL" --format '{{.Names}} {{.Status}}' ;;
  *) echo 'Usage: run_codex_tls_session.sh start|status|stop' >&2; exit 2 ;;
esac

#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${POC_TLS_OUTPUT:?Set a new output directory}"
[[ ! -e "$OUT" ]] || exit 2
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"
WORK="$(mktemp -d /tmp/poc-tls.XXXXXXXX)"
chmod 755 "$WORK"
ID="poc-tls-$(date +%s)-$$"
GATEWAY="$ID-gateway"
CLIENT="$ID-client"
cleanup() {
  docker rm -f "$CLIENT" "$GATEWAY" >/dev/null 2>&1 || true
  docker network rm "$ID-internal" "$ID-egress" >/dev/null 2>&1 || true
  rm -rf "$WORK"
}
trap cleanup EXIT
cp "$ROOT/tls_gateway.py" "$WORK/addon.py"
cp "$ROOT/scripts/probe_tls_gateway.py" "$WORK/probe.py"
chmod 644 "$WORK/"*.py
IMAGE='mitmproxy/mitmproxy:12.3.1@sha256:2711066c855659b5af8b1dbb84494ed3eff69b42ece439c60b4fe09a2db829d4'
docker image inspect "$IMAGE" --format '{{.Id}}' > "$OUT/gateway-image.txt"
docker image inspect local/gvisor-poc:latest --format '{{.Id}}' > "$OUT/client-image.txt"
sha256sum "$ROOT/tls_gateway.py" "$ROOT/scripts/probe_tls_gateway.py" "$ROOT/scripts/run_tls_gateway_smoke.sh" > "$OUT/source-sha256.txt"
docker info --format '{"kernel":{{json .KernelVersion}},"architecture":{{json .Architecture}},"engine":{{json .ServerVersion}}}' > "$OUT/environment.json"
docker network create --internal "$ID-internal" >/dev/null
docker network create "$ID-egress" >/dev/null
docker run -d --name "$GATEWAY" --network "$ID-egress" --user 10001:10001 \
  --read-only --tmpfs /tmp:rw,nosuid,nodev,size=64m --cap-drop ALL --security-opt no-new-privileges \
  --cpus=1 --memory=512m --pids-limit=128 -e POC_ALLOWED_HOSTS=example.com,api.openai.com \
  -v "$WORK/addon.py:/opt/addon.py:ro" --entrypoint mitmdump "$IMAGE" -q --listen-port 3128 \
  --set confdir=/tmp/ca --set connection_strategy=lazy --set upstream_cert=false \
  --set rawtcp=false --set http2=false --set ssl_insecure=false --set validate_inbound_headers=true \
  -s /opt/addon.py >/dev/null
docker network connect "$ID-internal" "$GATEWAY"
IP="$(docker inspect "$GATEWAY" --format "{{(index .NetworkSettings.Networks \"$ID-internal\").IPAddress}}")"
for _ in $(seq 1 40); do
  if docker exec "$GATEWAY" cat /tmp/ca/mitmproxy-ca-cert.pem > "$WORK/ca.pem" 2>/dev/null; then break; fi
  sleep 0.25
done
[[ -s "$WORK/ca.pem" ]] || { docker logs "$GATEWAY"; exit 1; }
chmod 644 "$WORK/ca.pem"
failed=0
for runtime in runc runsc-stable-20261109; do
  docker run --rm --name "$CLIENT" --runtime "$runtime" --network "$ID-internal" \
    --read-only --tmpfs /tmp:size=64m --cap-drop ALL --security-opt no-new-privileges \
    --user 10001:10001 --memory=256m --pids-limit=128 \
    -v "$WORK/probe.py:/test/probe.py:ro" -v "$WORK/ca.pem:/test/ca.pem:ro" \
    -e "GATEWAY_IP=$IP" --entrypoint python3 local/gvisor-poc:latest /test/probe.py \
    > "$OUT/$runtime.json" || failed=1
done
docker logs "$GATEWAY" > "$OUT/gateway-decisions.jsonl" 2>&1
cat "$OUT/"*.json
exit "$failed"

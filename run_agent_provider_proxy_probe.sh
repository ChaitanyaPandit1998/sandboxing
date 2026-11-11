#!/usr/bin/env bash
set -euo pipefail

IMAGE="${POC_IMAGE:-local/gvisor-poc:latest}"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
CLIENT_NET="agent-client-${RUN_ID}"
EGRESS_NET="agent-egress-${RUN_ID}"
PROXY="agent-proxy-${RUN_ID}"
OUT="${AGENT_PROXY_OUTPUT:-results/agent-proxy-${RUN_ID}}"
ALLOWED_HOSTS="api.anthropic.com,claude.ai,claude.com,platform.claude.com,auth.openai.com,chatgpt.com"
mkdir -p "$OUT"

cleanup() {
  docker logs "$PROXY" > "$OUT/proxy-decisions.jsonl" 2>&1 || true
  docker rm -f "$PROXY" >/dev/null 2>&1 || true
  docker network rm "$CLIENT_NET" "$EGRESS_NET" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker info >/dev/null
docker network create --internal "$CLIENT_NET" >/dev/null
docker network create "$EGRESS_NET" >/dev/null
docker run -d --name "$PROXY" --network "$EGRESS_NET" \
  --cpus=1 --memory=128m --pids-limit=64 --read-only --tmpfs /tmp:size=16m \
  --security-opt no-new-privileges --cap-drop=ALL --user 10001:10001 \
  -e "POC_ALLOWED_HOSTS=$ALLOWED_HOSTS" --entrypoint python3 "$IMAGE" /opt/poc/allowlist_proxy.py >/dev/null
docker network connect --alias egress-proxy "$CLIENT_NET" "$PROXY"
PROXY_IP="$(docker inspect "$PROXY" | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["NetworkSettings"]["Networks"][sys.argv[1]]["IPAddress"])' "$CLIENT_NET")"
for _ in $(seq 1 20); do
  if docker exec "$PROXY" python3 -c 'import socket; s=socket.create_connection(("127.0.0.1",3128),timeout=1); s.close()' >/dev/null 2>&1; then
    break
  fi
  sleep 0.25
done

probe_proxy() {
  local runtime="$1" host="$2" port="$3" expected="$4"
  docker run --rm --network="$CLIENT_NET" --runtime="$runtime" \
    --cpus=1 --memory=128m --pids-limit=64 --read-only --tmpfs /tmp:size=16m \
    --security-opt no-new-privileges --cap-drop=ALL --user 10001:10001 \
    -e "PROXY_IP=$PROXY_IP" -e PROXY_PORT=3128 \
    --entrypoint python3 "$IMAGE" -c '
import os, socket, sys
host, port, expected = sys.argv[1], int(sys.argv[2]), sys.argv[3]
sock = socket.create_connection((os.environ["PROXY_IP"], int(os.environ["PROXY_PORT"])), timeout=12)
sock.settimeout(12)
sock.sendall(f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n\r\n".encode())
status = sock.recv(4096).split(b"\r\n", 1)[0].decode("ascii", "replace")
sock.close()
code = status.split()[1] if len(status.split()) > 1 else "000"
ok = (code == "200") if expected == "allow" else (code == "403")
print(f"host={host} port={port} proxy_status={code} expected={expected} pass={ok}")
sys.exit(0 if ok else 1)
' "$host" "$port" "$expected"
}

probe_direct_egress() {
  local runtime="$1"
  docker run --rm --network="$CLIENT_NET" --runtime="$runtime" \
    --cpus=1 --memory=128m --pids-limit=64 --read-only --tmpfs /tmp:size=16m \
    --security-opt no-new-privileges --cap-drop=ALL --user 10001:10001 \
    --entrypoint python3 "$IMAGE" -c '
import socket, sys
try:
    s = socket.create_connection(("1.1.1.1", 443), timeout=2)
except OSError as exc:
    print(f"direct_egress=blocked error={type(exc).__name__}")
else:
    s.close()
    print("direct_egress=UNEXPECTED")
    sys.exit(1)
'
}

probe_client_dns() {
  local runtime="$1"
  docker run --rm --network="$CLIENT_NET" --runtime="$runtime" \
    --cpus=1 --memory=128m --pids-limit=64 --read-only --tmpfs /tmp:size=16m \
    --security-opt no-new-privileges --cap-drop=ALL --user 10001:10001 \
    --entrypoint python3 "$IMAGE" -c '
import socket
try:
    answers = socket.getaddrinfo("example.org", 443, type=socket.SOCK_STREAM)
except OSError as exc:
    print(f"client_dns=blocked error={type(exc).__name__}")
else:
    print(f"client_dns=resolved address_count={len(answers)}")
'
}

for runtime in runc runsc; do
  echo "=== $runtime provider proxy checks ===" | tee -a "$OUT/checks.txt"
  for host in api.anthropic.com claude.ai claude.com platform.claude.com auth.openai.com chatgpt.com; do
    probe_proxy "$runtime" "$host" 443 allow | tee -a "$OUT/checks.txt"
  done
  probe_proxy "$runtime" example.org 443 deny | tee -a "$OUT/checks.txt"
  probe_proxy "$runtime" 1.1.1.1 443 deny | tee -a "$OUT/checks.txt"
  probe_proxy "$runtime" api.anthropic.com 8443 deny | tee -a "$OUT/checks.txt"
  probe_direct_egress "$runtime" | tee -a "$OUT/checks.txt"
  probe_client_dns "$runtime" | tee -a "$OUT/checks.txt"
done

cat > "$OUT/policy.json" <<EOF
{"allowed_hosts":"$ALLOWED_HOSTS","allowed_port":443,"client_network":"internal","proxy_only_egress":true,"model_requests_sent":false}
EOF
echo "Agent provider proxy evidence: $OUT"
echo "No credentials or model requests were used."

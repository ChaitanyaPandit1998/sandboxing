#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"
IMAGE="${POC_IMAGE:-local/gvisor-poc:latest}"
read -r -a RUNTIMES <<< "${POC_RUNTIMES:-runc runsc}"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
OUT="${POC_DNS_REBIND_OUTPUT:-results/dns-rebind-${RUN_ID}}"
CLIENT_NET="poc-dns-client-${RUN_ID}"
EGRESS_NET="poc-dns-egress-${RUN_ID}"
DNS="poc-dns-server-${RUN_ID}"
PROXY="poc-dns-proxy-${RUN_ID}"
if [[ "$OUT" != /* ]]; then OUT="$ROOT/$OUT"; fi
if [[ -e "$OUT" ]]; then echo "Output path already exists: $OUT" >&2; exit 2; fi
mkdir -p "$OUT"

cleanup() {
  docker rm -f "$PROXY" "$DNS" >/dev/null 2>&1 || true
  docker network rm "$CLIENT_NET" "$EGRESS_NET" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker info >/dev/null
docker build --pull -t "$IMAGE" "$ROOT"
docker network create --internal "$CLIENT_NET" >/dev/null
docker network create "$EGRESS_NET" >/dev/null

# This synthetic DNS service alternates example.com between 1.1.1.1 and 127.0.0.1.
docker run -d --name "$DNS" --network "$EGRESS_NET" \
  --cpus=0.25 --memory=64m --pids-limit=32 --read-only --tmpfs /tmp:size=8m \
  --security-opt no-new-privileges --cap-drop=ALL --cap-add=NET_BIND_SERVICE \
  --user 10001:10001 --entrypoint python3 "$IMAGE" /opt/poc/dns_rebind_server.py >/dev/null
DNS_IP="$(docker inspect "$DNS" | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["NetworkSettings"]["Networks"][sys.argv[1]]["IPAddress"])' "$EGRESS_NET")"

docker run -d --name "$PROXY" --network "$EGRESS_NET" --dns="$DNS_IP" \
  --cpus=0.5 --memory=128m --pids-limit=64 --read-only --tmpfs /tmp:size=16m \
  --security-opt no-new-privileges --cap-drop=ALL --user 10001:10001 \
  -e POC_ALLOWED_HOSTS=example.com --entrypoint python3 "$IMAGE" /opt/poc/allowlist_proxy.py >/dev/null
docker network connect "$CLIENT_NET" "$PROXY"
PROXY_IP="$(docker inspect "$PROXY" | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["NetworkSettings"]["Networks"][sys.argv[1]]["IPAddress"])' "$CLIENT_NET")"

for _ in $(seq 1 30); do
  if docker logs "$DNS" 2>&1 | grep -q 'dns-listening' && \
     docker exec "$PROXY" python3 -c 'import socket; s=socket.create_connection(("127.0.0.1",3128),timeout=1); s.close()' >/dev/null 2>&1; then
    break
  fi
  sleep 0.25
done

printf '{"target":"example.com","dns_answers":["1.1.1.1","127.0.0.1"],"client_network":"internal","proxy_egress":"bridge","runtime_scope":"%s"}\n' "${RUNTIMES[*]}" > "$OUT/topology.json"
for runtime in "${RUNTIMES[@]}"; do
  docker run --rm --runtime="$runtime" --network="$CLIENT_NET" \
    --cpus=0.5 --memory=128m --pids-limit=64 --read-only --tmpfs /tmp:size=16m \
    --security-opt no-new-privileges --cap-drop=ALL --user 10001:10001 \
    -e "POC_HTTPS_PROXY=http://$PROXY_IP:3128" "$IMAGE" dns-rebind-probe \
    > "$OUT/check-$runtime.json"
done
docker logs "$DNS" > "$OUT/dns-answers.jsonl" 2>&1
docker logs "$PROXY" > "$OUT/proxy-decisions.jsonl" 2>&1
python3 - "$OUT" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
for result_path in sorted(root.glob("check-*.json")):
    runtime = result_path.stem.removeprefix("check-")
    result = json.loads(result_path.read_text())
    if not result.get("passed"):
        raise SystemExit(f"DNS rebinding probe failed under {runtime}")
    print(f"{runtime}: DNS rebinding blocked ({result['observations']['first_proxy_status']} then {result['observations']['second_proxy_status']})")
print(f"Evidence: {root}")
PY

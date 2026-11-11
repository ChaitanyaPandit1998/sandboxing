#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"
IMAGE="${POC_IMAGE:-local/gvisor-poc:latest}"
read -r -a RUNTIMES <<< "${POC_RUNTIMES:-runc runsc}"
ALLOWED_HOSTS="${POC_ALLOWED_HOSTS:-example.com}"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
CLIENT_NET="poc-client-${RUN_ID}"
EGRESS_NET="poc-egress-${RUN_ID}"
PROXY="poc-proxy-${RUN_ID}"
OUT="${POC_NETWORK_OUTPUT:-results/network-${RUN_ID}}"

if [[ -e "$OUT" ]]; then
  echo "Output path already exists: $OUT" >&2
  exit 2
fi
mkdir -p "$OUT"
cleanup() {
  docker rm -f "$PROXY" >/dev/null 2>&1 || true
  docker network rm "$CLIENT_NET" "$EGRESS_NET" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker info >/dev/null
docker build --pull -t "$IMAGE" "$ROOT"

# The workload network has no external route. Only the proxy joins both networks.
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

printf '{"allowed_hosts":"%s","allowed_port":443,"client_network":"internal","proxy_ip":"%s","proxy_egress":"Docker bridge","direct_client_egress":"blocked by internal network"}\n' \
  "$ALLOWED_HOSTS" "$PROXY_IP" > "$OUT/topology.json"

for runtime in "${RUNTIMES[@]}"; do
  echo "Checking HTTPS allowlist under $runtime"
  optional_probe_env=()
  if [[ -n "${POC_REDIRECT_TEST_URL:-}" ]]; then
    optional_probe_env+=(-e "POC_REDIRECT_TEST_URL=$POC_REDIRECT_TEST_URL")
  fi
  docker run --rm --runtime="$runtime" --network="$CLIENT_NET" \
    --cpus=1 --memory=256m --pids-limit=128 --read-only --tmpfs /tmp:size=64m \
    --security-opt no-new-privileges --cap-drop=ALL --user 10001:10001 \
    -e "POC_HTTPS_PROXY=http://$PROXY_IP:3128" "${optional_probe_env[@]}" "$IMAGE" network-probe \
    > "$OUT/check-$runtime.json"
done

docker logs "$PROXY" > "$OUT/proxy-decisions.jsonl" 2>&1
python3 - "$OUT" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
for result_path in sorted(root.glob("check-*.json")):
    runtime = result_path.stem.removeprefix("check-")
    result = json.loads(result_path.read_text())
    if not result.get("passed"):
        raise SystemExit(f"Network policy probes failed under {runtime}")
    print(f"{runtime}: {sum(result['checks'].values())}/{len(result['checks'])} network checks passed")
PY
echo "Allowlist probe evidence: $OUT"
echo "The proxy allows exact HTTPS hostnames in POC_ALLOWED_HOSTS on port 443; workload containers have no direct egress."
echo "This tests policy behavior with public example domains, not a production proxy deployment."

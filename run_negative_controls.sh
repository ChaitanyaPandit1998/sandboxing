#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
IMAGE="${POC_IMAGE:-local/gvisor-poc:latest}"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
OUT="${POC_NEGATIVE_OUTPUT:-results/negative-${RUN_ID}}"
if [[ "$OUT" != /* ]]; then OUT="$ROOT/$OUT"; fi
MARKER="$OUT/synthetic-mounted-marker"
CLIENT_NET="poc-negative-client-${RUN_ID}"
EGRESS_NET="poc-negative-egress-${RUN_ID}"
PROXY="poc-negative-proxy-${RUN_ID}"

if [[ -e "$OUT" ]]; then
  echo "Output path already exists: $OUT" >&2
  exit 2
fi
mkdir -p "$OUT"
printf 'synthetic negative-control marker; not a credential\n' > "$MARKER"
chmod 600 "$MARKER"

cleanup() {
  docker rm -f "poc-negative-${RUN_ID}-"* >/dev/null 2>&1 || true
  docker rm -f "$PROXY" >/dev/null 2>&1 || true
  docker network rm "$CLIENT_NET" "$EGRESS_NET" >/dev/null 2>&1 || true
  rm -f "$MARKER"
}
trap cleanup EXIT

docker info >/dev/null
docker build --pull -t "$IMAGE" "$ROOT"

run_case() {
  local runtime="$1" case_name="$2"
  shift 2
  local name="poc-negative-${RUN_ID}-${runtime}-${case_name}"
  local dir="$OUT/${runtime}-${case_name}"
  mkdir -p "$dir"
  local cid
  cid="$(docker create --name="$name" "$@")"
  docker inspect "$cid" > "$dir/inspect.json"
  set +e
  docker start -a "$cid" > "$dir/probe.json" 2> "$dir/container-stderr.txt"
  local status=$?
  set -e
  docker rm "$cid" >/dev/null
  python3 - "$ROOT" "$runtime" "$case_name" "$dir" "$status" "$OUT/negative-controls.jsonl" <<'PY'
import json, pathlib, sys
sys.path.insert(0, sys.argv[1])
from safety_validation import evaluate_launch_config
runtime, case_name, directory, status, output = sys.argv[2:]
root = pathlib.Path(directory)
probe = json.loads((root / "probe.json").read_text())
inspect = json.loads((root / "inspect.json").read_text())[0]
config_checks, _launch = evaluate_launch_config(inspect)
if case_name == "root-user":
    detected = not probe["checks"]["non_root_uid"] and not config_checks["configured_non_root_user"]
    signal = "non_root_uid=false; configured user is root"
elif case_name == "writable-rootfs":
    detected = not probe["checks"]["rootfs_write_blocked"] and not config_checks["root_filesystem_read_only"]
    signal = "rootfs_write_blocked=false; ReadonlyRootfs=false"
elif case_name == "synthetic-bind":
    detected = not probe["checks"]["guest_sentinel_not_visible"] and not config_checks["no_host_bind_mounts"]
    signal = "guest_sentinel_not_visible=false; host bind configured"
elif case_name == "added-capability":
    detected = not probe["checks"]["effective_capabilities_dropped"] and not config_checks["all_capabilities_dropped"]
    signal = "effective capability mask is nonzero; CAP_CHOWN granted"
else:
    raise SystemExit(f"unknown negative-control case {case_name}")
row = {"runtime": runtime, "scenario": case_name, "detected": bool(detected), "signal": signal, "probe_exit": int(status)}
with open(output, "a") as stream:
    stream.write(json.dumps(row, sort_keys=True) + "\n")
print(json.dumps(row, sort_keys=True))
if not detected or int(status) == 0:
    raise SystemExit(f"Negative control {case_name} was not detected under {runtime}")
PY
}

for runtime in runc runsc; do
  common=(--runtime="$runtime" --network=none --cpus=1 --memory=256m --pids-limit=128
    --tmpfs /tmp:size=64m --security-opt no-new-privileges --cap-drop=ALL)
  run_case "$runtime" root-user "${common[@]}" --read-only --user 0:0 "$IMAGE" probe
  run_case "$runtime" added-capability "${common[@]}" --read-only --user 0:0 --cap-add=CHOWN "$IMAGE" probe
  run_case "$runtime" writable-rootfs "${common[@]}" --user 10001:10001 "$IMAGE" probe
  run_case "$runtime" synthetic-bind "${common[@]}" --read-only --user 10001:10001 \
    --mount "type=bind,src=$MARKER,dst=/mnt/poc-negative-marker,readonly" \
    -e POC_SENTINEL_PATH=/mnt/poc-negative-marker "$IMAGE" probe
done

# A deliberately dual-homed workload can reach the proxy and has a direct
# bridge route. The allowlist probe must catch that bypass opportunity.
docker network create --internal "$CLIENT_NET" >/dev/null
docker network create "$EGRESS_NET" >/dev/null
docker run -d --name "$PROXY" --network "$EGRESS_NET" \
  --cpus=1 --memory=128m --pids-limit=64 --read-only --tmpfs /tmp:size=16m \
  --security-opt no-new-privileges --cap-drop=ALL --user 10001:10001 \
  -e POC_ALLOWED_HOSTS=example.com --entrypoint python3 "$IMAGE" /opt/poc/allowlist_proxy.py >/dev/null
docker network connect "$CLIENT_NET" "$PROXY"
PROXY_CLIENT_IP="$(docker inspect "$PROXY" | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["NetworkSettings"]["Networks"][sys.argv[1]]["IPAddress"])' "$CLIENT_NET")"
for _ in $(seq 1 20); do
  if docker exec "$PROXY" python3 -c 'import socket; s=socket.create_connection(("127.0.0.1",3128),timeout=1); s.close()' >/dev/null 2>&1; then break; fi
  sleep 0.25
done

for runtime in runc runsc; do
  name="poc-negative-${RUN_ID}-${runtime}-dual-homed"
  dir="$OUT/${runtime}-dual-homed"
  mkdir -p "$dir"
  cid="$(docker create --name="$name" --runtime="$runtime" --network="$EGRESS_NET" \
    --cpus=1 --memory=256m --pids-limit=128 --read-only --tmpfs /tmp:size=64m \
    --security-opt no-new-privileges --cap-drop=ALL --user 10001:10001 \
    -e "POC_HTTPS_PROXY=http://$PROXY_CLIENT_IP:3128" "$IMAGE" network-probe)"
  docker network connect "$CLIENT_NET" "$cid"
  docker inspect "$cid" > "$dir/inspect.json"
  set +e
  docker start -a "$cid" > "$dir/probe.json" 2> "$dir/container-stderr.txt"
  status=$?
  set -e
  docker rm "$cid" >/dev/null
  python3 - "$runtime" "$dir" "$status" "$OUT/negative-controls.jsonl" <<'PY'
import json, pathlib, sys
runtime, directory, status, output = sys.argv[1:]
root = pathlib.Path(directory)
probe = json.loads((root / "probe.json").read_text())
checks = probe["checks"]
detected = checks.get("allowlisted_https_succeeds") and not checks.get("direct_egress_blocked")
row = {"runtime": runtime, "scenario": "dual-homed-direct-egress", "detected": bool(detected),
       "signal": "allowlisted proxy works; direct egress is available", "probe_exit": int(status)}
with open(output, "a") as stream:
    stream.write(json.dumps(row, sort_keys=True) + "\n")
print(json.dumps(row, sort_keys=True))
if not detected or int(status) == 0:
    raise SystemExit("Network negative control was not detected; direct egress must be reachable for this control")
PY
done

docker logs "$PROXY" > "$OUT/proxy-decisions.jsonl" 2>&1
echo "All negative controls were detected. Evidence: $OUT/negative-controls.jsonl"
echo "Only synthetic temporary containers, networks, and a synthetic marker were used."

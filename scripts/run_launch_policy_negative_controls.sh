#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"
IMAGE="${POC_IMAGE:-local/gvisor-poc:latest}"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
OUT="${POC_LAUNCH_NEGATIVE_OUTPUT:-results/launch-negative-${RUN_ID}}"
if [[ "$OUT" != /* ]]; then OUT="$ROOT/$OUT"; fi
if [[ -e "$OUT" ]]; then echo "Output path already exists: $OUT" >&2; exit 2; fi
mkdir -p "$OUT"
CONTAINERS=()
MARKER="$OUT/synthetic-writable-mount-marker"
printf 'synthetic marker only\n' > "$MARKER"
cleanup() {
  for name in "${CONTAINERS[@]}"; do docker rm -f "$name" >/dev/null 2>&1 || true; done
  rm -f "$MARKER"
}
trap cleanup EXIT

docker info >/dev/null
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "Required image is missing: $IMAGE (build it with: docker build -t $IMAGE .)" >&2
  exit 2
fi

run_case() {
  local runtime="$1" scenario="$2" expected="$3"
  shift 3
  local name="poc-launch-negative-${RUN_ID}-${runtime}-${scenario}"
  local dir="$OUT/${runtime}-${scenario}"
  mkdir -p "$dir"
  local cid
  cid="$(docker create --name="$name" --runtime="$runtime" \
    --cpus=1 --memory=256m --pids-limit=128 --read-only --tmpfs /tmp:size=16m \
    --security-opt no-new-privileges --cap-drop=ALL --user 10001:10001 \
    "$@" --entrypoint /bin/true "$IMAGE")"
  CONTAINERS+=("$name")
  docker inspect "$cid" > "$dir/inspect.json"
  python3 - "$runtime" "$scenario" "$expected" "$dir/inspect.json" "$OUT/launch-negative-controls.jsonl" <<'PY'
import json, sys
runtime, scenario, expected, inspect_path, output = sys.argv[1:]
obj = json.load(open(inspect_path, encoding="utf-8"))[0]
host = obj["HostConfig"]
checks = {
    "privileged": bool(host.get("Privileged")),
    "host-pid": host.get("PidMode") == "host",
    "host-network": host.get("NetworkMode") == "host",
    "device-access": bool(host.get("Devices")),
    "writable-bind": any(m.get("Type") == "bind" and m.get("RW") for m in obj.get("Mounts", [])),
}
detected = checks.get(scenario, False) == (expected == "present")
row = {"runtime": runtime, "scenario": scenario, "setting_observed": checks.get(scenario),
       "detected": bool(detected), "container_started": False,
       "method": "Docker create/inspect only; workload was not started"}
with open(output, "a", encoding="utf-8") as f:
    f.write(json.dumps(row, sort_keys=True) + "\n")
print(json.dumps(row, sort_keys=True))
if not detected:
    raise SystemExit(f"Launch-policy negative control not detected: {runtime}/{scenario}")
PY
  docker rm "$cid" >/dev/null
}

for runtime in runc runsc; do
  # These intentionally unsafe configurations are inspected but never started.
  run_case "$runtime" privileged present --privileged
  run_case "$runtime" host-pid present --pid=host
  run_case "$runtime" host-network present --network=host
  run_case "$runtime" device-access present --device=/dev/null:/dev/poc-null:rwm
  run_case "$runtime" writable-bind present --mount "type=bind,src=$MARKER,dst=/mnt/poc-marker,readonly=false"
done

echo "All launch-policy negative controls detected from Docker configuration. No test workload was started. Evidence: $OUT/launch-negative-controls.jsonl"

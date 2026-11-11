#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"
IMAGE="${POC_IMAGE:-local/gvisor-poc:latest}"
read -r -a RUNTIMES <<< "${POC_RUNTIMES:-runc runsc}"
RUNSC_BIN="${RUNSC_BIN:-runsc}"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
OUT="${POC_SYSCALL_COMPAT_OUTPUT:-results/syscall-compat-${RUN_ID}}"
if [[ "$OUT" != /* ]]; then OUT="$ROOT/$OUT"; fi
if [[ -e "$OUT" ]]; then echo "Output path already exists: $OUT" >&2; exit 2; fi
mkdir -p "$OUT"
docker info >/dev/null
docker build --pull -t "$IMAGE" "$ROOT"
docker version --format '{{.Server.Version}}' > "$OUT/docker-engine-version.txt"
"$RUNSC_BIN" --version > "$OUT/runsc-version.txt"

cleanup() {
  for runtime in "${RUNTIMES[@]}"; do docker rm -f "poc-syscall-compat-${runtime}-${RUN_ID}" >/dev/null 2>&1 || true; done
  rm -f "$OUT/.inspect.json" "$OUT/.probe.json"
}
trap cleanup EXIT

for runtime in "${RUNTIMES[@]}"; do
  name="poc-syscall-compat-${runtime}-${RUN_ID}"
  cid="$(docker create --name="$name" --runtime="$runtime" --network=none \
    --cpus=1 --memory=256m --pids-limit=128 --read-only --tmpfs /tmp:size=64m \
    --security-opt no-new-privileges --cap-drop=ALL --user 10001:10001 "$IMAGE" syscall-compatibility)"
  docker inspect "$cid" > "$OUT/.inspect.json"
  docker start -a "$cid" > "$OUT/.probe.json"
  cp "$OUT/.probe.json" "$OUT/probe-$runtime.json"
  python3 "$ROOT/safety_validation.py" "$runtime" "$OUT/.probe.json" "$OUT/.inspect.json" "$OUT/checks.jsonl" > "$OUT/validation-$runtime.json"
  docker rm "$cid" >/dev/null
done

echo "Common syscall compatibility smoke passed under ${RUNTIMES[*]}. Evidence: $OUT"
echo "This checks selected everyday Linux APIs, not the full gVisor compatibility suite or escape resistance."

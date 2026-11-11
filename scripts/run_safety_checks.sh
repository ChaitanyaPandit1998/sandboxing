#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"
IMAGE="${POC_IMAGE:-local/gvisor-poc:latest}"
read -r -a RUNTIMES <<< "${POC_RUNTIMES:-runc runsc}"
OUT="${POC_SAFETY_OUTPUT:-results/safety-$(date -u +%Y%m%dT%H%M%SZ)}"
MARKER="$HOME/.gvisor-poc-host-sentinel"
RUN_ID="$$"

if [[ -e "$OUT" ]]; then
  echo "Output path already exists: $OUT" >&2
  exit 2
fi
mkdir -p "$OUT"
cleanup() {
  for runtime in "${RUNTIMES[@]}"; do docker rm -f "poc-safety-${runtime}-${RUN_ID}" >/dev/null 2>&1 || true; done
  rm -f "$MARKER" "$OUT/.probe.json" "$OUT/.inspect.json"
}
trap cleanup EXIT

docker info >/dev/null
docker build --pull -t "$IMAGE" "$ROOT"
printf 'synthetic visibility marker; not a credential\n' > "$MARKER"
chmod 600 "$MARKER"

for runtime in "${RUNTIMES[@]}"; do
  name="poc-safety-${runtime}-${RUN_ID}"
  cid="$(docker create --name="$name" --runtime="$runtime" --network=none --cpus=1 --memory=256m --pids-limit=128 \
    --read-only --tmpfs /tmp:size=64m --security-opt no-new-privileges --cap-drop=ALL \
    --user 10001:10001 -e "POC_SENTINEL_PATH=$MARKER" "$IMAGE" probe)"
  docker inspect "$cid" > "$OUT/.inspect.json"
  docker start -a "$cid" > "$OUT/.probe.json"

  python3 "$ROOT/safety_validation.py" "$runtime" "$OUT/.probe.json" "$OUT/.inspect.json" "$OUT/checks.jsonl"
  docker rm "$cid" >/dev/null
done

echo "Boundary checks passed under ${RUNTIMES[*]}. Evidence: $OUT/checks.jsonl"
echo "These checks verify selected controls; they are not a security proof."

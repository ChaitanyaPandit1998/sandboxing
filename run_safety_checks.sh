#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
IMAGE="${POC_IMAGE:-local/gvisor-poc:latest}"
OUT="${POC_SAFETY_OUTPUT:-results/safety-$(date -u +%Y%m%dT%H%M%SZ)}"
MARKER="$HOME/.gvisor-poc-host-sentinel"

if [[ -e "$OUT" ]]; then
  echo "Output path already exists: $OUT" >&2
  exit 2
fi
mkdir -p "$OUT"
trap 'rm -f "$MARKER" "$OUT/.probe.json"' EXIT

docker info >/dev/null
docker build --pull -t "$IMAGE" "$ROOT"
printf 'synthetic visibility marker; not a credential\n' > "$MARKER"
chmod 600 "$MARKER"

for runtime in runc runsc; do
  docker run --rm --runtime="$runtime" --network=none --cpus=1 --memory=256m --pids-limit=128 \
    --read-only --tmpfs /tmp:size=64m --security-opt no-new-privileges --cap-drop=ALL \
    --user 10001:10001 -e "POC_SENTINEL_PATH=$MARKER" "$IMAGE" probe > "$OUT/.probe.json"

  python3 - "$runtime" "$OUT/.probe.json" "$OUT/checks.jsonl" <<'PY'
import json, sys
runtime, probe_path, output_path = sys.argv[1:]
with open(probe_path) as f:
    probe = json.load(f)
row = {"runtime": runtime, **probe}
with open(output_path, "a") as f:
    f.write(json.dumps(row, sort_keys=True) + "\n")
print(json.dumps(row, indent=2, sort_keys=True))
if not probe.get("passed"):
    raise SystemExit(f"A safe isolation/compatibility check failed under {runtime}")
PY
done

rm -f "$OUT/.probe.json"
echo "Safe isolation/compatibility checks passed for both runtimes. Evidence: $OUT/checks.jsonl"
echo "These probes check selected properties; they are not a security proof."

#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
IMAGE="${POC_IMAGE:-local/gvisor-poc:latest}"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
OUT="${POC_SYSCALL_OUTPUT:-results/syscall-${RUN_ID}}"
if [[ "$OUT" != /* ]]; then OUT="$ROOT/$OUT"; fi
MARKER="$HOME/.gvisor-poc-syscall-sentinel"

if [[ -e "$OUT" || -e "$MARKER" ]]; then
  echo "Output or sentinel path already exists; refusing to overwrite it." >&2
  exit 2
fi
mkdir -p "$OUT"
printf 'synthetic syscall-matrix marker; not a credential\n' > "$MARKER"
chmod 600 "$MARKER"

cleanup() {
  for runtime in runc runsc; do docker rm -f "poc-syscall-${runtime}-${RUN_ID}" >/dev/null 2>&1 || true; done
  rm -f "$MARKER" "$OUT/.probe.json" "$OUT/.inspect.json"
}
trap cleanup EXIT

docker info >/dev/null
docker build --pull -t "$IMAGE" "$ROOT"
docker info --format '{{json .SecurityOptions}}' > "$OUT/.security-options.json"
docker version --format '{{.Server.Version}}' > "$OUT/.engine-version.txt"
python3 - "$OUT" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
security = json.loads((root / ".security-options.json").read_text())
version = (root / ".engine-version.txt").read_text().strip()
(root / "engine.json").write_text(json.dumps({
    "docker_engine_version": version,
    "security_options": security,
    "seccomp_note": "Record the daemon-reported profile. If no seccomp profile is listed, verify daemon configuration; Docker normally applies its default profile unless overridden.",
}, indent=2, sort_keys=True) + "\n")
PY
rm -f "$OUT/.security-options.json" "$OUT/.engine-version.txt"

before_hash="$(python3 - "$MARKER" <<'PY'
import hashlib, pathlib, sys
print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())
PY
)"

for runtime in runc runsc; do
  name="poc-syscall-${runtime}-${RUN_ID}"
  cid="$(docker create --name="$name" --runtime="$runtime" --network=none \
    --cpus=1 --memory=256m --pids-limit=128 --read-only --tmpfs /tmp:size=64m \
    --security-opt no-new-privileges --cap-drop=ALL --user 10001:10001 \
    -e "POC_SYSCALL_SENTINEL_PATH=$MARKER" "$IMAGE" syscall-matrix)"
  docker inspect "$cid" > "$OUT/.inspect.json"
  docker start -a "$cid" > "$OUT/.probe.json"
  python3 "$ROOT/safety_validation.py" "$runtime" "$OUT/.probe.json" "$OUT/.inspect.json" "$OUT/matrix.jsonl"
  after_hash="$(python3 - "$MARKER" <<'PY'
import hashlib, pathlib, sys
print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())
PY
)"
  [[ "$before_hash" == "$after_hash" ]] || { echo "Synthetic guest marker changed under $runtime" >&2; exit 1; }
  python3 - "$runtime" "$after_hash" "$OUT/host-state.jsonl" <<'PY'
import json, sys
runtime, digest, output = sys.argv[1:]
with open(output, "a") as stream:
    stream.write(json.dumps({"runtime": runtime, "synthetic_guest_marker_sha256": digest, "unchanged": True}, sort_keys=True) + "\n")
PY
  docker rm "$cid" >/dev/null
done

echo "Syscall matrix captured for runc and runsc: $OUT/matrix.jsonl"
echo "These non-destructive probes record outcomes; they do not test or prove escape resistance."

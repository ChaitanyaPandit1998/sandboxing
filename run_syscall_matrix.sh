#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
IMAGE="${POC_IMAGE:-local/gvisor-poc:latest}"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
OUT="${POC_SYSCALL_OUTPUT:-results/syscall-${RUN_ID}}"
read -r -a RUNTIMES <<< "${POC_SYSCALL_RUNTIMES:-runc runsc}"
if [[ "$OUT" != /* ]]; then OUT="$ROOT/$OUT"; fi
MARKER="$HOME/.gvisor-poc-syscall-sentinel"
CUSTOM_PROFILE="$ROOT/profiles/syscall-probe-v29.9.3.json"

if [[ -e "$OUT" || -e "$MARKER" ]]; then
  echo "Output or sentinel path already exists; refusing to overwrite it." >&2
  exit 2
fi
mkdir -p "$OUT"
printf 'synthetic syscall-matrix marker; not a credential\n' > "$MARKER"
chmod 600 "$MARKER"

cleanup() {
  for runtime in "${RUNTIMES[@]}"; do
    for mode in builtin-default custom-probe-overlay; do
      docker rm -f "poc-syscall-${runtime}-${mode}-${RUN_ID}" >/dev/null 2>&1 || true
    done
  done
  rm -f "$MARKER" "$OUT/.probe.json" "$OUT/.inspect.json"
}
trap cleanup EXIT

docker info >/dev/null
docker build --pull -t "$IMAGE" "$ROOT"
python3 "$ROOT/generate_syscall_probe_profile.py" > "$OUT/profile-metadata.json"
CUSTOM_PROFILE_SHA256="$(python3 - "$CUSTOM_PROFILE" <<'PY'
import hashlib, pathlib, sys
print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())
PY
)"
docker info --format '{{json .SecurityOptions}}' > "$OUT/.security-options.json"
docker version --format '{{.Server.Version}}' > "$OUT/.engine-version.txt"
if ! sysctl -n vm.unprivileged_userfaultfd > "$OUT/.userfaultfd-sysctl.txt" 2>/dev/null; then
  printf 'unavailable\n' > "$OUT/.userfaultfd-sysctl.txt"
fi
if ! sysctl -n kernel.perf_event_paranoid > "$OUT/.perf-paranoid-sysctl.txt" 2>/dev/null; then
  printf 'unavailable\n' > "$OUT/.perf-paranoid-sysctl.txt"
fi
python3 - "$OUT" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
security = json.loads((root / ".security-options.json").read_text())
version = (root / ".engine-version.txt").read_text().strip()
uffd_setting = (root / ".userfaultfd-sysctl.txt").read_text().strip()
perf_setting = (root / ".perf-paranoid-sysctl.txt").read_text().strip()
profile = json.loads((root / "profile-metadata.json").read_text())
if version != "29.9.3":
    raise SystemExit(f"Expected Docker Engine 29.9.3 for the pinned profile comparison, got {version}")
if "name=seccomp,profile=builtin" not in security:
    raise SystemExit("Docker is not reporting its built-in seccomp profile; refusing a mismatched comparison")
(root / "engine.json").write_text(json.dumps({
    "docker_engine_version": version,
    "security_options": security,
    "custom_profile_source": profile["source_url"],
    "custom_profile_source_sha256": profile["source_sha256"],
    "custom_profile_sha256": profile["derived_profile_sha256"],
    "custom_profile_added_syscalls": profile["additional_unconditional_allow_syscalls"],
    "host_vm_unprivileged_userfaultfd": uffd_setting,
    "host_kernel_perf_event_paranoid": perf_setting,
    "seccomp_note": "Each runtime is measured once with Docker's reported built-in profile and once with the hash-pinned derived profile. The derived profile retains Docker's default deny behavior and adds unconditional allow rules only for the listed probe syscalls.",
}, indent=2, sort_keys=True) + "\n")
PY
rm -f "$OUT/.security-options.json" "$OUT/.engine-version.txt" "$OUT/.userfaultfd-sysctl.txt" "$OUT/.perf-paranoid-sysctl.txt" "$OUT/profile-metadata.json"

before_hash="$(python3 - "$MARKER" <<'PY'
import hashlib, pathlib, sys
print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())
PY
)"

for runtime in "${RUNTIMES[@]}"; do
  for mode in builtin-default custom-probe-overlay; do
    name="poc-syscall-${runtime}-${mode}-${RUN_ID}"
    security_options=(--security-opt no-new-privileges)
    profile_hash=""
    if [[ "$mode" == "custom-probe-overlay" ]]; then
      security_options+=(--security-opt "seccomp=$CUSTOM_PROFILE")
      profile_hash="$CUSTOM_PROFILE_SHA256"
    fi
    cid="$(docker create --name="$name" --runtime="$runtime" --network=none \
      --cpus=1 --memory=256m --pids-limit=128 --read-only --tmpfs /tmp:size=64m \
      "${security_options[@]}" --cap-drop=ALL --user 10001:10001 \
      -e "POC_SYSCALL_SENTINEL_PATH=$MARKER" \
      -e "POC_SYSCALL_SECCOMP_MODE=$mode" \
      -e "POC_SYSCALL_PROFILE_SHA256=$profile_hash" \
      "$IMAGE" syscall-matrix)"
    docker inspect "$cid" > "$OUT/.inspect.json"
    docker start -a "$cid" > "$OUT/.probe.json"
    python3 "$ROOT/safety_validation.py" "$runtime/$mode" "$OUT/.probe.json" "$OUT/.inspect.json" "$OUT/matrix.jsonl"
    after_hash="$(python3 - "$MARKER" <<'PY'
import hashlib, pathlib, sys
print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())
PY
    )"
    [[ "$before_hash" == "$after_hash" ]] || { echo "Synthetic guest marker changed under $runtime/$mode" >&2; exit 1; }
    python3 - "$runtime" "$mode" "$after_hash" "$OUT/host-state.jsonl" <<'PY'
import json, sys
runtime, mode, digest, output = sys.argv[1:]
with open(output, "a") as stream:
    stream.write(json.dumps({"runtime": runtime, "seccomp_mode": mode, "synthetic_guest_marker_sha256": digest, "unchanged": True}, sort_keys=True) + "\n")
PY
    docker rm "$cid" >/dev/null
  done
done

echo "Syscall matrix captured for both runtimes and both seccomp profiles: $OUT/matrix.jsonl"
echo "These non-destructive probes record outcomes; they do not test or prove escape resistance."

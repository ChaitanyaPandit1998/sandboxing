#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
IMAGE="${POC_IMAGE:-local/gvisor-poc:latest}"
OUT="${POC_SAFETY_OUTPUT:-results/safety-$(date -u +%Y%m%dT%H%M%SZ)}"
MARKER="$HOME/.gvisor-poc-host-sentinel"
RUN_ID="$$"

if [[ -e "$OUT" ]]; then
  echo "Output path already exists: $OUT" >&2
  exit 2
fi
mkdir -p "$OUT"
cleanup() {
  for runtime in runc runsc; do docker rm -f "poc-safety-${runtime}-${RUN_ID}" >/dev/null 2>&1 || true; done
  rm -f "$MARKER" "$OUT/.probe.json" "$OUT/.inspect.json"
}
trap cleanup EXIT

docker info >/dev/null
docker build --pull -t "$IMAGE" "$ROOT"
printf 'synthetic visibility marker; not a credential\n' > "$MARKER"
chmod 600 "$MARKER"

for runtime in runc runsc; do
  name="poc-safety-${runtime}-${RUN_ID}"
  cid="$(docker create --name="$name" --runtime="$runtime" --network=none --cpus=1 --memory=256m --pids-limit=128 \
    --read-only --tmpfs /tmp:size=64m --security-opt no-new-privileges --cap-drop=ALL \
    --user 10001:10001 -e "POC_SENTINEL_PATH=$MARKER" "$IMAGE" probe)"
  docker inspect "$cid" > "$OUT/.inspect.json"
  docker start -a "$cid" > "$OUT/.probe.json"

  python3 - "$runtime" "$OUT/.probe.json" "$OUT/.inspect.json" "$OUT/checks.jsonl" <<'PY'
import json, sys
runtime, probe_path, inspect_path, output_path = sys.argv[1:]
probe = json.load(open(probe_path))
inspect = json.load(open(inspect_path))[0]
host = inspect["HostConfig"]
container_user = (inspect.get("Config") or {}).get("User", "")
security = host.get("SecurityOpt") or []
cap_drop = host.get("CapDrop") or []
cap_add = host.get("CapAdd") or []
binds = host.get("Binds") or []
devices = host.get("Devices") or []
mounts = host.get("Mounts") or []
config_checks = {
    "not_privileged": not host.get("Privileged", False),
    "no_host_bind_mounts": len(binds) == 0 and len(mounts) == 0,
    "no_host_devices": len(devices) == 0,
    "no_host_namespaces": all(host.get(key, "") != "host" for key in ("PidMode", "IpcMode", "NetworkMode", "UTSMode")),
    "all_capabilities_dropped": "ALL" in cap_drop and len(cap_add) == 0,
    "root_filesystem_read_only": host.get("ReadonlyRootfs", False),
    "no_new_privileges_configured": any("no-new-privileges" in item for item in security),
    "configured_non_root_user": container_user == "10001:10001",
    "network_is_none": host.get("NetworkMode", "") == "none",
}
all_checks = {**probe.get("checks", {}), **config_checks}
row = {
    "runtime": runtime,
    "work": probe.get("work"),
    "checks": all_checks,
    "observations": probe.get("observations", {}),
    "launch_config": {
        "user": container_user,
        "network_mode": host.get("NetworkMode"),
        "pid_mode": host.get("PidMode") or "private default",
        "ipc_mode": host.get("IpcMode") or "private default",
        "privileged": host.get("Privileged", False),
        "cap_drop": cap_drop,
        "cap_add": cap_add,
        "binds": binds,
        "devices": devices,
        "readonly_rootfs": host.get("ReadonlyRootfs", False),
        "security_options": security,
    },
}
row["passed"] = probe.get("passed", False) and all(all_checks.values())
with open(output_path, "a") as f:
    f.write(json.dumps(row, sort_keys=True) + "\n")
print(json.dumps(row, indent=2, sort_keys=True))
if not row["passed"]:
    raise SystemExit(f"A safe boundary check failed under {runtime}")
PY
  docker rm "$cid" >/dev/null
done

echo "Boundary checks passed for both runtimes. Evidence: $OUT/checks.jsonl"
echo "These checks verify selected controls; they are not a security proof."

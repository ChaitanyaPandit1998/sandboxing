#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
IMAGE="${POC_IMAGE:-local/gvisor-poc:latest}"
TRIALS="${POC_TRIALS:-20}"
OUT="${POC_OUTPUT:-results/$(date -u +%Y%m%dT%H%M%SZ)}"
DEFAULT_WORKLOADS="cpu io http http-keepalive http-keepalive-nodelay http-concurrent-keepalive http-concurrent-keepalive-nodelay"
WORKLOADS="${POC_WORKLOADS:-$DEFAULT_WORKLOADS}"
read -r -a WORKLOAD_ARRAY <<< "$WORKLOADS"
if [[ ${#WORKLOAD_ARRAY[@]} -eq 0 ]]; then
  echo "POC_WORKLOADS must contain at least one workload" >&2
  exit 2
fi
for work in "${WORKLOAD_ARRAY[@]}"; do
  case "$work" in
    cpu|io|http|http-keepalive|http-keepalive-nodelay|http-concurrent-keepalive|http-concurrent-keepalive-nodelay) ;;
    *) echo "Unsupported workload in POC_WORKLOADS: $work" >&2; exit 2 ;;
  esac
done

if ! [[ "$TRIALS" =~ ^[1-9][0-9]*$ ]]; then
  echo "POC_TRIALS must be a positive integer" >&2
  exit 2
fi
if [[ -e "$OUT" ]]; then
  echo "Output path already exists: $OUT" >&2
  exit 2
fi
mkdir -p "$OUT"

docker info >/dev/null
docker build --pull -t "$IMAGE" "$ROOT"

python3 - "$OUT/environment.json" "$IMAGE" "$TRIALS" <<'PY'
import json, os, platform, subprocess, sys

def cmd(*args):
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT).strip()
    except Exception as exc:
        return f"unavailable: {exc}"

image, trials = sys.argv[2], int(sys.argv[3])
workloads = os.environ.get("POC_WORKLOADS", "cpu io http http-keepalive http-keepalive-nodelay http-concurrent-keepalive http-concurrent-keepalive-nodelay").split()
info = json.loads(cmd("docker", "info", "--format", "{{json .}}"))
runtimes = json.loads(cmd("docker", "info", "--format", "{{json .Runtimes}}"))
image_info = json.loads(cmd("docker", "image", "inspect", image))[0]
data = {
    "captured_utc": cmd("date", "-u", "+%Y-%m-%dT%H:%M:%SZ"),
    "os_release": cmd("sh", "-c", ". /etc/os-release && printf '%s %s' \"$PRETTY_NAME\" \"$VERSION_ID\""),
    "kernel": platform.release(),
    "architecture": platform.machine(),
    "logical_cpus": os.cpu_count(),
    "memory": cmd("sh", "-c", "awk '/MemTotal/ {print $2 \" kB\"}' /proc/meminfo"),
    "docker_engine": info.get("ServerVersion"),
    "docker_architecture": info.get("Architecture"),
    "docker_os": info.get("OperatingSystem"),
    "docker_cgroup_driver": info.get("CgroupDriver"),
    "docker_cgroup_version": info.get("CgroupVersion"),
    "docker_default_runtime": info.get("DefaultRuntime"),
    "docker_runtimes": sorted(runtimes),
    "runc_version": cmd("runc", "--version"),
    "runsc_version": cmd("runsc", "--version"),
    "workload_image": image,
    "workload_image_id": image_info.get("Id"),
    "workload_image_repo_digests": image_info.get("RepoDigests", []),
    "workloads": workloads,
    "configured_limits": {"cpus": 1, "memory": "256m", "pids": 128, "network": "none", "rootfs": "read-only", "tmpfs": "/tmp:size=64m", "user": "10001:10001", "no_new_privileges": True},
    "warmup_runs_per_runtime_workload": 1,
    "measured_trials_per_runtime_workload": trials,
    "trial_order": "alternates runtime order each trial; workload order reverses on even trials",
}
with open(sys.argv[1], "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PY

docker info --format '{{json .Runtimes}}' > "$OUT/runtimes.json"

run_one() {
  local runtime="$1" work="$2" phase="$3" trial="$4"
  local start_ns end_ns wall_ns result_file
  result_file="$OUT/.result.json"
  start_ns="$(date +%s%N)"
  if [[ "$runtime" == "runc" ]]; then
    docker run --rm --network=none --cpus=1 --memory=256m --pids-limit=128 \
      --read-only --tmpfs /tmp:size=64m --security-opt no-new-privileges \
      --user 10001:10001 "$IMAGE" "$work" > "$result_file"
  else
    docker run --rm --network=none --runtime=runsc --cpus=1 --memory=256m --pids-limit=128 \
      --read-only --tmpfs /tmp:size=64m --security-opt no-new-privileges \
      --user 10001:10001 "$IMAGE" "$work" > "$result_file"
  fi
  end_ns="$(date +%s%N)"
  wall_ns=$((end_ns - start_ns))
  python3 - "$runtime" "$work" "$phase" "$trial" "$wall_ns" "$result_file" "$OUT/${phase}.jsonl" <<'PY'
import json, sys
runtime, work, phase, trial, wall_ns, result_path, out_path = sys.argv[1:]
with open(result_path) as f:
    result = json.load(f)
row = {"runtime": runtime, "work": work, "phase": phase, "trial": int(trial),
       "container_wall_seconds": int(wall_ns) / 1e9, "result": result}
with open(out_path, "a") as f:
    f.write(json.dumps(row, sort_keys=True) + "\n")
PY
  rm -f "$result_file"
}

for work in "${WORKLOAD_ARRAY[@]}"; do
  for runtime in runc runsc; do
    echo "warmup runtime=$runtime work=$work"
    run_one "$runtime" "$work" warmup 0
  done
done

for trial in $(seq 1 "$TRIALS"); do
  if (( trial % 2 == 1 )); then runtimes=(runc runsc); else runtimes=(runsc runc); fi
  if (( trial % 2 == 1 )); then
    works=("${WORKLOAD_ARRAY[@]}")
  else
    works=()
    for ((idx=${#WORKLOAD_ARRAY[@]}-1; idx>=0; idx--)); do works+=("${WORKLOAD_ARRAY[idx]}"); done
  fi
  for runtime in "${runtimes[@]}"; do
    for work in "${works[@]}"; do
      echo "trial=$trial runtime=$runtime work=$work"
      run_one "$runtime" "$work" raw "$trial"
    done
  done
done

python3 - "$OUT/raw.jsonl" "$OUT/summary.json" <<'PY'
import json, statistics, sys

groups = {}
for line in open(sys.argv[1]):
    row = json.loads(line)
    key = (row["runtime"], row["work"])
    groups.setdefault(key, []).append(row)

summary = []
for (runtime, work), rows in sorted(groups.items()):
    workload = [r["result"]["seconds"] for r in rows]
    wall = [r["container_wall_seconds"] for r in rows]
    summary.append({
        "runtime": runtime,
        "work": work,
        "trials": len(rows),
        "workload_median_seconds": statistics.median(workload),
        "workload_p25_seconds": statistics.quantiles(workload, n=4)[0] if len(workload) >= 4 else min(workload),
        "workload_p75_seconds": statistics.quantiles(workload, n=4)[2] if len(workload) >= 4 else max(workload),
        "container_wall_median_seconds": statistics.median(wall),
        "container_wall_p25_seconds": statistics.quantiles(wall, n=4)[0] if len(wall) >= 4 else min(wall),
        "container_wall_p75_seconds": statistics.quantiles(wall, n=4)[2] if len(wall) >= 4 else max(wall),
    })
with open(sys.argv[2], "w") as f:
    json.dump(summary, f, indent=2)
    f.write("\n")
print(json.dumps(summary, indent=2))
PY

echo "Environment and results: $OUT"

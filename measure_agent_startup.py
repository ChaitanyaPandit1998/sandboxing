#!/usr/bin/env python3
"""Measure cached-image CLI process startup under paired runc/runsc containers."""

import argparse
import json
import math
import os
import platform
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def percentile(values, p):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(p * len(ordered)) - 1)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default="local/agent-session:claude-2.1.322-codex-0.167.1")
    parser.add_argument("--trials", type=int, default=50)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    meta = {
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "host_kernel": platform.release(),
        "host_architecture": platform.machine(),
        "image": args.image,
        "trials_per_cli_runtime": args.trials,
        "cli_versions": {"claude": "2.1.322", "codex": "0.167.1"},
        "network": "none",
        "limits": {"cpus": 1, "memory": "256m", "pids": 128, "rootfs": "read-only", "user": "10001:10001", "capabilities": "all dropped", "no_new_privileges": True},
        "metric": "docker run process wall time including container create, CLI version command, and removal; image already present",
    }
    rows = []
    for trial in range(1, args.trials + 1):
        runtime_order = ["runc", "runsc"] if trial % 2 else ["runsc", "runc"]
        cli_order = ["claude", "codex"] if trial % 2 else ["codex", "claude"]
        for runtime in runtime_order:
            for cli in cli_order:
                command = [
                    "docker", "run", "--rm", "--network=none", f"--runtime={runtime}",
                    "--cpus=1", "--memory=256m", "--pids-limit=128", "--read-only",
                    "--tmpfs", "/tmp:size=64m,uid=10001,gid=10001",
                    "--tmpfs", "/home/agent:size=64m,uid=10001,gid=10001",
                    "--tmpfs", "/workspace:size=256m,uid=10001,gid=10001",
                    "--cap-drop=ALL", "--security-opt=no-new-privileges", "--user", "10001:10001",
                    args.image, cli, "--version",
                ]
                start = time.monotonic_ns()
                proc = subprocess.run(command, capture_output=True, text=True)
                elapsed = (time.monotonic_ns() - start) / 1e9
                rows.append({
                    "trial": trial,
                    "runtime": runtime,
                    "cli": cli,
                    "wall_seconds": elapsed,
                    "exit_code": proc.returncode,
                    "stdout": proc.stdout.strip(),
                    "stderr": proc.stderr.strip()[:2000],
                })
                print(f"trial={trial}/{args.trials} runtime={runtime} cli={cli} wall={elapsed:.3f}s exit={proc.returncode}", flush=True)

    summary = []
    for runtime in ("runc", "runsc"):
        for cli in ("claude", "codex"):
            selected = [row for row in rows if row["runtime"] == runtime and row["cli"] == cli]
            times = [row["wall_seconds"] for row in selected]
            summary.append({
                "runtime": runtime,
                "cli": cli,
                "trials": len(selected),
                "successful": sum(row["exit_code"] == 0 for row in selected),
                "p50_seconds": percentile(times, 0.50),
                "p95_seconds": percentile(times, 0.95),
                "max_seconds": max(times),
            })
    bundle = {"environment": meta, "summary": summary, "trials": rows}
    args.output.write_text(json.dumps(bundle, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()

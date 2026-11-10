#!/usr/bin/env python3
"""Shared Docker launch-configuration checks for the safety runners."""

import json
import sys


def evaluate_launch_config(inspect):
    host = inspect["HostConfig"]
    container_user = (inspect.get("Config") or {}).get("User", "")
    security = host.get("SecurityOpt") or []
    cap_drop = host.get("CapDrop") or []
    cap_add = host.get("CapAdd") or []
    binds = host.get("Binds") or []
    devices = host.get("Devices") or []
    mounts = inspect.get("Mounts") or []
    bind_mounts = [mount for mount in mounts if mount.get("Type") == "bind"]
    checks = {
        "not_privileged": not host.get("Privileged", False),
        "no_host_bind_mounts": len(binds) == 0 and len(bind_mounts) == 0,
        "no_host_devices": len(devices) == 0,
        "no_host_namespaces": all(host.get(key, "") != "host" for key in ("PidMode", "IpcMode", "NetworkMode", "UTSMode")),
        "all_capabilities_dropped": "ALL" in cap_drop and len(cap_add) == 0,
        "root_filesystem_read_only": host.get("ReadonlyRootfs", False),
        "no_new_privileges_configured": any("no-new-privileges" in item for item in security),
        "configured_non_root_user": container_user == "10001:10001",
        "network_is_none": host.get("NetworkMode", "") == "none",
    }
    launch = {
        "user": container_user,
        "network_mode": host.get("NetworkMode"),
        "pid_mode": host.get("PidMode") or "private default",
        "ipc_mode": host.get("IpcMode") or "private default",
        "privileged": host.get("Privileged", False),
        "cap_drop": cap_drop,
        "cap_add": cap_add,
        "binds": binds,
        "mounts": [{"type": mount.get("Type"), "destination": mount.get("Destination"), "rw": mount.get("RW")} for mount in mounts],
        "devices": devices,
        "readonly_rootfs": host.get("ReadonlyRootfs", False),
        "security_options": security,
    }
    return checks, launch


def build_row(runtime, probe, inspect):
    config_checks, launch = evaluate_launch_config(inspect)
    checks = {**probe.get("checks", {}), **config_checks}
    row = {
        "runtime": runtime,
        "work": probe.get("work"),
        "checks": checks,
        "observations": probe.get("observations", {}),
        "launch_config": launch,
    }
    row["passed"] = probe.get("passed", False) and all(checks.values())
    return row


def main(argv):
    runtime, probe_path, inspect_path, output_path = argv[1:]
    with open(probe_path, encoding="utf-8") as stream:
        probe = json.load(stream)
    with open(inspect_path, encoding="utf-8") as stream:
        inspect = json.load(stream)[0]
    row = build_row(runtime, probe, inspect)
    with open(output_path, "a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, sort_keys=True) + "\n")
    print(json.dumps(row, indent=2, sort_keys=True))
    if not row["passed"]:
        raise SystemExit(f"A safe boundary check failed under {runtime}")


if __name__ == "__main__":
    main(sys.argv)

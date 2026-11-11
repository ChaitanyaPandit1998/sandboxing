#!/usr/bin/env python3
"""Derive a narrow syscall-probe profile from Docker Engine 29.9.3's default."""

import copy
import hashlib
import json
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "profiles/docker-seccomp-default-v29.9.3.json"
OUTPUT = ROOT / "profiles/syscall-probe-v29.9.3.json"
METADATA = ROOT / "profiles/syscall-probe-v29.9.3.metadata.json"
EXPECTED_SHA256 = "785b2429264afba4d594320337cb17f144f3c7d51585f9805eef72e28f4f9334"
SOURCE_URL = (
    "https://raw.githubusercontent.com/moby/moby/docker-v29.9.3/"
    "vendor/github.com/moby/profiles/seccomp/default.json"
)

# ptrace is already allowed by the matching Docker profile on this guest's
# Linux 4.8+ kernel. These are the probe syscalls otherwise denied by default.
EXTRA_PROBE_SYSCALLS = ["bpf", "keyctl", "mount", "perf_event_open", "unshare", "userfaultfd"]


def main():
    source_bytes = SOURCE.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    if source_hash != EXPECTED_SHA256:
        raise SystemExit(f"Docker default profile hash mismatch: {source_hash}")
    profile = json.loads(source_bytes)
    if profile.get("defaultAction") != "SCMP_ACT_ERRNO":
        raise SystemExit("Unexpected default seccomp action; refusing to derive profile")
    custom = copy.deepcopy(profile)
    custom["syscalls"].append({"names": EXTRA_PROBE_SYSCALLS, "action": "SCMP_ACT_ALLOW"})
    OUTPUT.write_text(json.dumps(custom, indent=2) + "\n")
    metadata = {
        "source_engine_tag": "docker-v29.9.3",
        "source_url": SOURCE_URL,
        "source_sha256": source_hash,
        "derived_profile_sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        "additional_unconditional_allow_syscalls": EXTRA_PROBE_SYSCALLS,
        "ptrace_note": "Not changed; already allowed by the upstream profile for Linux >= 4.8.",
        "warning": "For isolated, invalid-argument syscall probes only; not a production seccomp profile.",
    }
    METADATA.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    print(json.dumps(metadata, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

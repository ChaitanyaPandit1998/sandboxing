#!/usr/bin/env python3
"""Derive a POC-only bubblewrap seccomp profile from Docker 29.9.3 default."""

import copy
import hashlib
import json
import pathlib


ROOT = pathlib.Path(__file__).resolve().parent
SOURCE = ROOT / "profiles/docker-seccomp-default-v29.9.3.json"
OUTPUT = ROOT / "profiles/bwrap-seccomp-v29.9.3.json"
METADATA = ROOT / "profiles/bwrap-seccomp-v29.9.3.metadata.json"
EXPECTED_SHA256 = "785b2429264afba4d594320337cb17f144f3c7d51585f9805eef72e28f4f9334"
SOURCE_URL = (
    "https://raw.githubusercontent.com/moby/moby/docker-v29.9.3/"
    "vendor/github.com/moby/profiles/seccomp/default.json"
)

# Permit only the namespaces needed by the POC's bwrap profile: mount, user,
# PID, network, IPC, and UTS. Keep cgroup and time namespaces blocked.
# clone() flags are argument 0 on the POC's ARM64 guest; unshare() flags are
# argument 0 on all Linux architectures.
CLONE_NEWCGROUP = 0x02000000
CLONE_NEWTIME = 0x00000080
DISALLOWED_NAMESPACE_MASK = CLONE_NEWCGROUP | CLONE_NEWTIME


def main():
    source_bytes = SOURCE.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    if source_hash != EXPECTED_SHA256:
        raise SystemExit(f"Docker default profile hash mismatch: {source_hash}")

    profile = json.loads(source_bytes)
    if profile.get("defaultAction") != "SCMP_ACT_ERRNO":
        raise SystemExit("Unexpected default seccomp action; refusing to derive profile")
    custom = copy.deepcopy(profile)

    namespace_filter = {
        "index": 0,
        "value": DISALLOWED_NAMESPACE_MASK,
        "valueTwo": 0,
        "op": "SCMP_CMP_MASKED_EQ",
    }
    # Docker's default profile already has a conditional clone rule. Adding a
    # second rule for the same syscall does not reliably widen that rule when
    # Docker compiles the filter, so replace its ARM64 condition in place.
    # Preserve its capability and architecture exclusions.
    clone_rules = [
        rule
        for rule in custom["syscalls"]
        if "clone" in rule.get("names", [])
        and "s390" in rule.get("excludes", {}).get("arches", [])
        and rule.get("args")
    ]
    if len(clone_rules) != 1:
        raise SystemExit(f"Expected one non-s390 Docker clone rule, found {len(clone_rules)}")
    clone_rules[0]["args"] = [namespace_filter]
    # Moby's per-rule includes.arches values use Go architecture names (e.g.
    # "arm64"), not libseccomp architecture tokens such as SCMP_ARCH_AARCH64.
    clone_rules[0]["includes"] = {"arches": ["arm64"]}

    custom["syscalls"].extend(
        [
            {
                "names": ["unshare"],
                "action": "SCMP_ACT_ALLOW",
                "args": [namespace_filter],
            },
            {
                "names": ["mount", "umount2", "pivot_root"],
                "action": "SCMP_ACT_ALLOW",
            },
        ]
    )

    OUTPUT.write_text(json.dumps(custom, indent=2) + "\n")
    metadata = {
        "source_engine_tag": "docker-v29.9.3",
        "source_url": SOURCE_URL,
        "source_sha256": source_hash,
        "derived_profile_sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        "purpose": "Disposable POC probe for Codex/bubblewrap nested namespaces under Docker.",
        "added_rules": {
            "clone": "ARM64 only; allows mount, user, PID, network, IPC, and UTS namespace flags; keeps cgroup and time namespace flags denied.",
            "unshare": "Allows the same namespace subset; keeps cgroup and time namespace flags denied.",
            "mount_umount_pivot_root": "Allowed so bubblewrap can assemble its private mount tree. Linux still applies namespace capability checks; these operations require CAP_SYS_ADMIN in the owning mount namespace.",
        },
        "unchanged_restrictions": [
            "defaultAction remains SCMP_ACT_ERRNO",
            "clone3 remains at the Docker default (ENOSYS without CAP_SYS_ADMIN)",
            "setns remains denied by the Docker default",
            "no Linux capabilities are added by this profile",
        ],
        "scope_warning": "Test only in the disposable POC VM. Seccomp applies to every process in the container, not only /usr/bin/bwrap. Any process can create the allowed nested namespaces and attempt namespace-scoped mounts. Keep the outer container non-root, drop all capabilities, retain no-new-privileges and AppArmor, and do not use this profile in production without a separate security review.",
    }
    METADATA.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    print(json.dumps(metadata, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

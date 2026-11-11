# Syscall probe seccomp profiles

`docker-seccomp-default-v29.9.3.json` is copied unmodified from the Moby `docker-v29.9.3` tag:

<https://raw.githubusercontent.com/moby/moby/docker-v29.9.3/vendor/github.com/moby/profiles/seccomp/default.json>

SHA-256: `785b2429264afba4d594320337cb17f144f3c7d51585f9805eef72e28f4f9334`.

`scripts/generate_syscall_probe_profile.py` verifies that digest and creates `syscall-probe-v29.9.3.json` by appending one unconditional allow rule for six harmless syscall probes. The default action remains `SCMP_ACT_ERRNO`; Docker's other rules are preserved. `ptrace` is not added because the upstream profile already allows it on Linux 4.8 and later.

This derived profile is only for the isolated, invalid-argument probe matrix. It is not a production profile. The source profile is from the Moby project and is distributed under Apache-2.0; see <https://github.com/moby/moby/blob/docker-v29.9.3/LICENSE>.

## Bubblewrap compatibility probe

`scripts/generate_bwrap_seccomp_profile.py` verifies the same pinned source digest and writes `bwrap-seccomp-v29.9.3.json`. It retains Docker's default-deny action, `clone3` behavior, and `setns` denial; it replaces Docker's existing ARM64 `clone` rule and adds an `unshare` rule that permit only mount, user, PID, network, IPC, and UTS namespace flags (cgroup/time namespace flags remain blocked). It also allows `mount`, `umount2`, and `pivot_root` so bubblewrap can assemble its private mount tree. No Linux capabilities are added.

This profile applies to every process in the container, not just bubblewrap. Any process can create the permitted nested namespaces and attempt namespace-scoped mounts. Use it only in the disposable POC VM with a non-root container, dropped capabilities, `no-new-privileges`, read-only root, and AppArmor still enabled. It is a compatibility probe, not a production security profile. On the current VM, bwrap's fresh `/proc` mount is rejected by the kernel with `VFS: Mount too revealing`; the seccomp profile does not override that VFS restriction.

The generated profile's SHA-256 and full scope notes are in `bwrap-seccomp-v29.9.3.metadata.json`.

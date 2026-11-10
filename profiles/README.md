# Syscall probe seccomp profiles

`docker-seccomp-default-v29.9.3.json` is copied unmodified from the Moby `docker-v29.9.3` tag:

<https://raw.githubusercontent.com/moby/moby/docker-v29.9.3/vendor/github.com/moby/profiles/seccomp/default.json>

SHA-256: `785b2429264afba4d594320337cb17f144f3c7d51585f9805eef72e28f4f9334`.

`generate_syscall_probe_profile.py` verifies that digest and creates `syscall-probe-v29.9.3.json` by appending one unconditional allow rule for six harmless syscall probes. The default action remains `SCMP_ACT_ERRNO`; Docker's other rules are preserved. `ptrace` is not added because the upstream profile already allows it on Linux 4.8 and later.

This derived profile is only for the isolated, invalid-argument probe matrix. It is not a production profile. The source profile is from the Moby project and is distributed under Apache-2.0; see <https://github.com/moby/moby/blob/docker-v29.9.3/LICENSE>.

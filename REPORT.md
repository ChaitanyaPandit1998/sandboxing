# Initial experiment report

Date: 2026-11-10 (UTC)

## Environment

- Lima 2.3.0 on an Apple Silicon Mac
- Ubuntu 26.04.1 LTS, ARM64, kernel 7.0.0-38-generic
- Docker Engine 29.9.3
- `runsc` release-20261102.0
- Python 3.12.16, pinned `python:3.12-slim` image digest
- 1 CPU, 256 MiB memory, 128 PID limit; no network; read-only image root; `/tmp` tmpfs; non-root user
- Three trials per workload/runtime, with `runc` trials run before `runsc` trials

## Run 1: exploratory three-trial run

| Workload | `runc` median | `runsc` median | `runsc` difference |
| --- | ---: | ---: | ---: |
| CPU: 300,000 SHA-256 iterations | 61.72 ms | 69.38 ms | +12.4% |
| I/O: write/read 8 MiB in `/tmp` | 5.32 ms | 5.87 ms | +10.3% |
| HTTP: 200 serial loopback requests | 546.51 ms | 703.13 ms | +28.7% |

Raw samples and medians are in `results/20261110T151337Z/`. This run used a fixed runtime order and no warm-up; the following run supersedes it for performance interpretation.

## Run 2: warmed, alternating 20-trial run

The revised runner performs one warm-up for each runtime/workload pair, alternates which runtime runs first on each trial, reverses workload order every other trial, and captures both workload time and total `docker run` wall time. Each workload/runtime pair has 20 measured samples. Environment details are saved in `results/20261110T152643Z/environment.json`, raw measurements in `raw.jsonl`, and quartiles/medians in `summary.json`.

### Workload time

| Workload | `runc` median (p25–p75) | `runsc` median (p25–p75) | `runsc` median difference |
| --- | ---: | ---: | ---: |
| CPU | 63.46 ms (62.74–64.19) | 68.33 ms (66.53–71.09) | +7.7% |
| I/O to `/tmp` | 4.85 ms (4.72–4.93) | 5.58 ms (5.51–5.68) | +15.0% |
| 200 loopback HTTP requests | 544.69 ms (543.62–546.69) | 698.40 ms (668.83–710.80) | +28.2% |

### End-to-end `docker run` wall time

| Workload | `runc` median | `runsc` median | `runsc` median difference |
| --- | ---: | ---: | ---: |
| CPU | 255.90 ms | 312.63 ms | +22.2% |
| I/O | 201.43 ms | 247.37 ms | +22.8% |
| HTTP | 774.17 ms | 973.06 ms | +25.7% |

In this VM and workload set, `runsc` was slower on all three workload timers and all three end-to-end timers. The P25–P75 ranges do not overlap for these samples, but this remains one machine and one run; it is not a general performance claim.

## Interpretation and limits

Both runtimes completed all workloads in the same ARM64 Ubuntu Lima VM with matched Docker limits. The second run reduces order bias and captures container start/stop overhead, but the workloads are synthetic and only 20 trials were collected. The I/O case uses a memory-backed `/tmp`, so it says nothing about durable storage performance. `container_wall_seconds` includes Docker container create/start/stop, but excludes image build and pull because the image is built before the measurements. These results do not measure exploit resistance or establish a security conclusion.

For a stronger performance comparison, repeat this protocol across multiple VM boots and increase workload duration to reduce timer overhead. For security evaluation, define a threat model and test specific isolation properties independently of these timings.

## Safe isolation and compatibility probes

Date: 2026-11-10. The same probe image ran under both runtimes with 1 CPU, 256 MiB RAM, 128 PIDs, `--network=none`, read-only root, 64 MiB `/tmp`, UID 10001, `no-new-privileges`, and all Linux capabilities dropped. All 11 checks passed under both `runc` and `runsc`.

| Area | Probe | `runc` | `runsc` |
| --- | --- | --- | --- |
| Process | Workload is PID 1; `/proc` exposes only PID 1 | Pass | Pass |
| Identity | Workload runs as non-root UID 10001 | Pass | Pass |
| Guest filesystem visibility | Synthetic marker in guest home is not visible in container | Pass | Pass |
| Root filesystem | Write to image path is denied with `EROFS` | Pass | Pass |
| Temporary filesystem | Write under `/tmp` succeeds | Pass | Pass |
| Procfs and syscalls | Read `/proc/1/status`, `getrandom`, anonymous `mmap`, thread create/join | Pass | Pass |
| Networking | Loopback socket works; external connection to a documentation-only address is blocked | Pass | Pass |

Raw probe output is in `results/safety-20261110T155834Z/checks.jsonl`. These are configuration regression checks for one benign process. They do not attempt container escapes, kernel exploitation, or malicious workloads, and they do not establish that either runtime is secure.

## Expanded boundary and egress policy checks

Date: 2026-11-10. Follow-up checks used the same guest, pinned workload image, and runtime limits. The safety runner inspected Docker's saved launch configuration as well as the process's observed state. Both `runc` and `runsc` passed all 25 checks; evidence is in `results/safety-20261110T180847Z/checks.jsonl`.

| Area | Result under both runtimes |
| --- | --- |
| Privilege | UID 10001, effective capability mask zero, `no_new_privs=1`, and an attempted `setuid(0)` was denied |
| Sudo | `sudo` is absent from this minimal image; the process also cannot switch to UID 0 via `setuid` |
| Host boundary | No bind mounts, devices, privileged mode, host namespaces, or visible Docker socket; a synthetic guest-home marker was not visible |
| Filesystem/process | Read-only root rejects writes (`EROFS`), `/tmp` remains writable, and only PID 1 appears in the container's proc view |
| Networking | Safety probe uses Docker `network=none`; loopback works and external access is blocked |

The sudo result is specifically “sudo unavailable and privilege escalation probes denied”; this does not test a separately installed sudo binary. The synthetic marker is not a real sensitive file and no host home directory is mounted into the VM.

The separate allowlist test uses two Docker networks: the workload joins an internal-only network, while the proxy joins that network and a bridge network. The workload has no direct egress route. The proxy allows exact host `example.com` on TCP 443, resolves the hostname and rejects non-global destination addresses, and records decisions. Both runtimes passed 5/5 checks in `results/network-20261110T180956Z-19376/`:

| Probe | `runc` | `runsc` |
| --- | --- | --- |
| HTTPS to `example.com:443` succeeds through proxy (HTTP 200) | Pass | Pass |
| HTTPS to `example.org:443` is denied | Pass | Pass |
| Proxy request to IP literal `1.1.1.1:443` is denied | Pass | Pass |
| Proxy request to `example.com:8443` is denied | Pass | Pass |
| Direct workload egress to `1.1.1.1:443` is blocked | Pass | Pass |

This validates the demonstrated policy path with a public example domain. It does not establish resilience to hostile proxy clients, covert channels, proxy compromise, or production domain-filtering requirements. Treat the proxy as trusted infrastructure and enforce real egress policy at the network boundary as well. These probes are not a substitute for security review or adversarial testing.

## Negative controls for probe sensitivity

Date: 2026-11-11 IST (2026-11-10 UTC). Deliberately weakened, temporary containers were used to check whether the probes fail when selected controls are absent. All ten cases were detected across `runc` and `runsc`; summary evidence is in `results/negative-20261110T185453Z-24675/negative-controls.jsonl`. After the negative run, the normal configuration passed all 25 checks on both runtimes again; see `results/safety-20261110T185500Z/checks.jsonl`.

| Deliberate change | Detection signal | `runc` | `runsc` |
| --- | --- | --- | --- |
| Run the workload as UID 0 | Non-root probe fails and launch-config validator rejects the configured user | Detected | Detected |
| Grant `CAP_CHOWN` to a root test process | Effective capability probe and launch-config validator detect the grant | Detected | Detected |
| Make the image root writable | Rootfs write succeeds and `ReadonlyRootfs` is false | Detected | Detected |
| Bind mount a synthetic marker file | Marker becomes visible and launch-config validator detects a bind mount | Detected | Detected |
| Give workload a direct bridge route alongside the proxy network | Allowlisted proxy request still works, while direct egress succeeds and the bypass probe fails | Detected | Detected |

The bind-mount control exposed a checker gap: Docker reports mounts created with `--mount` in the top-level inspect `Mounts` field, not only in `HostConfig.Binds`. The shared validator now checks both representations, and the negative control imports that same validator. No real host files, credentials, privileged containers, or host namespaces were used. These cases test selected probe sensitivity and do not constitute adversarial testing.

## Kernel-interface syscall matrix

Date: 2026-11-11 IST (2026-11-10 UTC). Seven non-destructive probes were run under the same container policy on the ARM64 Lima guest: UID 10001, no capabilities, `no_new_privileges`, read-only root, and no network. Docker Engine 29.9.3 reported `seccomp,profile=builtin` and `apparmor,profile=default`; the active Docker seccomp profile can therefore account for shared denials. Full observations are in `results/syscall-20261110T192449Z-26740/matrix.jsonl`, with daemon settings in `engine.json` and unchanged synthetic marker hashes in `host-state.jsonl`.

| Probe | `runc` observation | `runsc` observation |
| --- | --- | --- |
| Invalid-filesystem `mount` request | `EPERM` | `EPERM` |
| `unshare(CLONE_NEWNS)` in a short-lived child | `EPERM` | `EPERM` |
| Invalid `bpf` command | `EPERM` | `EPERM` |
| Invalid `keyctl` operation | `EPERM` | `ENOSYS` |
| Invalid `ptrace` request | `ESRCH` | `ESRCH` |
| `perf_event_open` with a null attribute pointer | `EPERM` | `ENODEV` |
| `userfaultfd` create-and-immediately-close | `EPERM` | `ENOSYS` |

The equal `EPERM` results are consistent with shared Docker filtering, while `ENOSYS` under `runsc` is consistent with an interface not being implemented there. These observations do not by themselves prove which layer produced a denial or show that one runtime is more secure. `ESRCH` and `ENODEV` are errors from deliberately invalid probes, not successful use of those interfaces. The userfaultfd probe closes its descriptor immediately if creation succeeds. Both runs observed the same SHA-256 for the synthetic guest marker afterward.

This is a small interface-behavior inventory, not syscall fuzzing or escape testing. A stronger comparison would require reviewed, version-specific test cases and host-side monitoring in a disposable VM, while retaining identical Docker security profiles and container settings. Docker documents its built-in seccomp profile as an allowlist that blocks selected system calls; see [Docker seccomp documentation](https://docs.docker.com/engine/security/seccomp).

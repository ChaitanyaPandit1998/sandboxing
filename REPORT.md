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

# Local gVisor POC

Compare Docker's default `runc` runtime with gVisor's `runsc` runtime on the same Lima Linux VM. This is a local engineering experiment, not a security certification.

![Architecture diagram showing the Mac host, Lima Linux VM, paired Docker runtime paths, and saved experiment results](architecture.svg)

## Current setup

- Host: Apple Silicon macOS
- VM: Lima ARM64 Ubuntu, rootful Docker Engine
- Runtimes: Docker default (`runc`) and gVisor (`runsc`)
- Workloads: dependency-free Python CPU, temporary-file I/O, and loopback HTTP
- Limits: 1 CPU, 256 MiB memory, 128 PIDs, no network, read-only root filesystem

The VM is dedicated to this POC and does not mount the host home directory. Workloads run as a non-root user with no-new-privileges. The runner warms up each runtime/workload pair once, alternates runtime order by trial, and performs 20 measured trials per pair by default. It records workload time and end-to-end `docker run` wall time, plus environment metadata and raw samples. The Python base image is pinned by digest.

## Status

The host has Go 1.27.3, Lima 2.3.0, and Docker Desktop. The guest uses Ubuntu 26.04.1, kernel 7.0.0-38-generic, Docker Engine 29.9.3, and gVisor 20261102.0. Both runtimes passed smoke checks and all selected safe isolation/compatibility probes. The refined run completed 20 trials per workload/runtime after warm-ups, alternating runtime order. See `REPORT.md` for results and limits.

## Files

- `architecture.svg`: host, VM, runtime, workload, and results flow.
- `Dockerfile`: creates the small Python workload image.
- `workload.py`: CPU, file I/O, and loopback HTTP synthetic workloads.
- `install_gvisor.sh`: adds the official gVisor apt repository and configures Docker inside Ubuntu.
- `run_experiments.sh`: warm-ups, alternating paired measurements, environment capture, and summary statistics. Set `POC_TRIALS` to change the default of 20.
- `run_safety_checks.sh`: checks selected filesystem, PID namespace, syscall, loopback, and network behaviors under both runtimes.

Create the VM with `limactl start --name=gvisor-poc --vm-type=vz --cpus=4 --memory=6 --disk=40 --mount-none template:docker-rootful`. From this repository's root, copy the project files into the guest:

```bash
limactl shell gvisor-poc -- mkdir -p /tmp/gvisor-poc
limactl copy -r Dockerfile README.md REPORT.md architecture.svg install_gvisor.sh run_experiments.sh run_safety_checks.sh workload.py gvisor-poc:/tmp/gvisor-poc/
limactl shell gvisor-poc -- sh -lc 'mkdir -p "$HOME/gvisor-poc" && cp -R /tmp/gvisor-poc/. "$HOME/gvisor-poc/"'
```

Then install gVisor and run the experiments inside the guest:

```bash
limactl shell gvisor-poc -- sh -lc 'cd "$HOME/gvisor-poc" && sudo bash install_gvisor.sh && bash run_experiments.sh'
limactl shell gvisor-poc -- sh -lc 'cd "$HOME/gvisor-poc" && bash run_safety_checks.sh'
```

Results are written under the project directory regardless of the caller's working directory. Each run saves `environment.json`, `runtimes.json`, `warmup.jsonl`, `raw.jsonl`, and `summary.json` in a timestamped results directory.

Run the selected safety/compatibility probes from the same guest with `bash run_safety_checks.sh`. They use a temporary synthetic marker outside the container and remove it on exit. Their containers also drop all Linux capabilities. They are regression probes for the configured boundaries, not an adversarial security assessment or a proof of isolation.

Do not compare results from Docker Desktop with results from the Lima VM. The experiment measures synthetic compatibility and speed only; it does not establish a security guarantee.

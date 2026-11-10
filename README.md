# Local gVisor POC

Compare Docker's default `runc` runtime with gVisor's `runsc` runtime on the same Lima Linux VM. This is a local engineering experiment, not a security certification.

![Architecture diagram showing the Mac host, Lima Linux VM, paired Docker runtime paths, and saved experiment results](architecture.svg)

## Current setup

- Host: Apple Silicon macOS
- VM: Lima ARM64 Ubuntu, rootful Docker Engine
- Runtimes: Docker default (`runc`) and gVisor (`runsc`)
- Workloads: dependency-free Python CPU, temporary-file I/O, and loopback HTTP
- Limits: 1 CPU, 256 MiB memory, 128 PIDs, read-only root filesystem

The VM is dedicated to this POC and does not mount the host home directory. Workloads run as a non-root user with no-new-privileges. Benchmark and baseline safety containers use no network; the separate allowlist test gives the workload an internal-only network and a single explicit proxy path. The runner warms up each runtime/workload pair once, alternates runtime order by trial, and performs 20 measured trials per pair by default. It records workload time and end-to-end `docker run` wall time, plus environment metadata and raw samples. The Python base image is pinned by digest.

## Status

The host has Go 1.27.3, Lima 2.3.0, and Docker Desktop. The guest uses Ubuntu 26.04.1, kernel 7.0.0-38-generic, Docker Engine 29.9.3, and gVisor 20261102.0. Both runtimes passed the smoke checks, 25 selected privilege/host-boundary checks, and five HTTPS allowlist checks. These are narrow configuration and policy probes, not a security assessment. The refined benchmark completed 20 trials per workload/runtime after warm-ups, alternating runtime order.

## Files

- `architecture.svg`: host, VM, runtime, workload, and results flow.
- `Dockerfile`: creates the small Python workload image.
- `.dockerignore`: keeps local results and tools out of the image build context.
- `workload.py`: CPU, file I/O, and loopback HTTP synthetic workloads.
- `install_gvisor.sh`: adds the official gVisor apt repository and configures Docker inside Ubuntu.
- `run_experiments.sh`: warm-ups, alternating paired measurements, environment capture, and summary statistics. Set `POC_TRIALS` to change the default of 20.
- `run_safety_checks.sh`: checks filesystem visibility, Docker launch configuration, PID namespace, privilege restrictions, syscalls, loopback, and no-network behavior under both runtimes.
- `allowlist_proxy.py`, `run_network_allowlist.sh`: check exact-host HTTPS allowlisting with an internal-only workload network and a proxy that alone has external bridge egress.

Create the VM with `limactl start --name=gvisor-poc --vm-type=vz --cpus=4 --memory=6 --disk=40 --mount-none template:docker-rootful`. From this repository's root, copy the project files into the guest:

```bash
limactl shell gvisor-poc -- mkdir -p /tmp/gvisor-poc
limactl copy -r .dockerignore Dockerfile README.md REPORT.md architecture.svg install_gvisor.sh run_experiments.sh run_safety_checks.sh run_network_allowlist.sh workload.py allowlist_proxy.py gvisor-poc:/tmp/gvisor-poc/
limactl shell gvisor-poc -- sh -lc 'mkdir -p "$HOME/gvisor-poc" && cp -R /tmp/gvisor-poc/. "$HOME/gvisor-poc/"'
```

Then install gVisor and run the experiments inside the guest:

```bash
limactl shell gvisor-poc -- sh -lc 'cd "$HOME/gvisor-poc" && sudo bash install_gvisor.sh && bash run_experiments.sh'
limactl shell gvisor-poc -- sh -lc 'cd "$HOME/gvisor-poc" && bash run_safety_checks.sh'
limactl shell gvisor-poc -- sh -lc 'cd "$HOME/gvisor-poc" && bash run_network_allowlist.sh'
```

Results are written under the project directory regardless of the caller's working directory. Each run saves `environment.json`, `runtimes.json`, `warmup.jsonl`, `raw.jsonl`, and `summary.json` in a timestamped results directory.

Run the selected safety/compatibility probes from the same guest with `bash run_safety_checks.sh`. They use a temporary synthetic marker outside the container and remove it on exit. Their containers also drop all Linux capabilities; the runner inspects Docker's container configuration to verify no host bind mounts, devices, privileged mode, or host namespaces were requested. The probes check non-root execution, effective capabilities, `no_new_privs`, denied `setuid(0)`, sudo absence/non-escalation, and Docker socket invisibility.

Run the separate allowlist test with `bash run_network_allowlist.sh`. By default it permits HTTPS to `example.com`, denies `example.org`, IP literals, and non-443 ports, and checks that the workload cannot bypass the proxy with direct egress. Only the trusted test proxy joins the external bridge network. Override the demonstration allowlist with `POC_ALLOWED_HOSTS`, and update the probe targets to match. The example-domain run is a policy-path check, not a production egress proxy recommendation.

All checks are narrow regression probes, not an adversarial security assessment or proof of isolation.

Do not compare results from Docker Desktop with results from the Lima VM. The experiment measures synthetic compatibility and speed only; it does not establish a security guarantee.

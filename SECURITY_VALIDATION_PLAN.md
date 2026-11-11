# Security validation plan

## Purpose and current confidence

This plan defines the next validation phase for the local gVisor POC. Current evidence shows that the configured `runc` and `runsc` containers passed selected isolation and network-policy checks, and that the harness detected the tested weakened configurations. It is useful evidence about configuration behavior and test sensitivity. It is not an adversarial security assessment or proof of escape resistance.

The goal of the next phase is to test specific boundaries under a defined attacker model, preserve reproducible evidence, and identify gaps before considering a production design. gVisor is designed to interpose a userspace application kernel between the workload and host kernel; its own security model also relies on host resource controls such as cgroups and separately configured network policy. Tests should cover those layers as well as the runtime. [gVisor security model](https://gvisor.dev/docs/architecture_guide/security/)

## Threat model

### Assume the workload attacker can

- Run arbitrary code as the configured unprivileged container user.
- Supply or influence application files and dependencies; for the stronger image-control case, build a malicious container image.
- Use supported system calls, threads, filesystem paths, sockets, and malformed application inputs available inside the container.
- Attempt to exhaust resources within the limits assigned to the container.

### Assume trusted for this phase

- The Mac host, Lima VM configuration, Linux host kernel, Docker daemon, runtime binaries, and experiment scripts are administered by the evaluator and kept patched.
- Docker launch configuration, runtime selection, resource limits, and mounted files are controlled by the trusted launcher.
- No host home directory, real credentials, production data, or Docker socket is mounted into the test containers.

If an agent or tenant can control the OCI configuration, runtime flags, Docker daemon, or VM administrator account, that is a different and stronger threat model and needs separate controls and testing.

### In scope

Host file and process isolation, privilege restrictions, direct and proxy-mediated network policy, selected resource exhaustion, runtime stability, workload compatibility, and evidence that the probes detect known configuration regressions.

### Out of scope for this POC

Exhaustive proof of security, hardware side-channel resistance, production multi-tenant certification, and proof that `runsc` is universally safer than `runc`. gVisor documents side channels and higher-level service vulnerabilities as areas its sandbox does not eliminate. [gVisor security introduction](https://gvisor.dev/docs/architecture_guide/intro/)

## Safe execution rules

- Run tests only in the disposable Lima VM. Take a VM snapshot or ensure it can be rebuilt before destructive or stress cases.
- Use synthetic marker files and dummy tokens only. Never expose credentials, host directories, or personal data to test containers.
- Keep Docker daemon changes, debug runtimes, fuzzing, and resource-exhaustion tests inside the VM; schedule daemon restarts while it is idle.
- Keep a host-side or VM-side watchdog and resource ceiling for stress tests. Stop a case if the guest becomes unresponsive.
- Record exact runtime, kernel, Docker, image digest, launch configuration, test input, output, and cleanup status for every run.
- Preserve failing cases as minimal reproductions. Do not turn a failure into a passing result by weakening the control under test.

## Prioritized test matrix

| Priority | Area | Test cases to add or repeat | Pass evidence |
| --- | --- | --- | --- |
| P0 | Harness and launch policy | Repeat current checks; add negative controls for privileged mode, host PID/network namespaces, device access, and an unexpected writable mount. Run under both runtimes. | The normal profile passes; each deliberately weakened setting is independently detected by observed state or inspected launch configuration. |
| P0 | Filesystem and process boundary | Try access to synthetic host-side markers at several paths; traversal and symlink cases; inspect `/proc`, `/sys`, `/dev`, and process visibility; attempt writes outside explicitly writable temporary storage. | No unmounted host marker or unapproved device is visible; writes outside allowed paths fail; process view matches the declared policy. |
| P0 | Egress and allowlist bypass | Retest allowed/denied domains, redirects, IP literals, DNS changes, IPv4/IPv6, alternate ports, and direct routes. Add UDP or other protocols only if the product requires them. | Only the declared destinations and protocols are reachable; direct bypass remains blocked; proxy decisions and network captures agree with the policy. |
| P0 | Privilege and kernel interface | Test the supported gVisor syscall/compatibility suite plus focused namespace, mount, ptrace, capability, and process probes using safe test cases. Keep the current invalid-argument matrix as a small diagnostic, not the coverage measure. Optionally collect the documented `runsc --strace` trace in the disposable VM to help interpret the existing matrix; keep it separate from benchmarks. | No workload gains host privilege or changes host state; unsupported calls fail in documented ways; runtime logs and probe output are retained. |
| P1 | Secrets and service endpoints | Place only synthetic credentials outside the sandbox; check environment, filesystem, metadata-service routes, runtime sockets, and proxy behavior for accidental exposure. | The workload can access only explicitly granted secrets and endpoints; no host or control-plane credential is reachable. |
| P1 | Resource exhaustion and cleanup | Bounded CPU, memory, process-count, temporary-disk, and timeout tests; kill and restart workloads; test cleanup after normal exit and forced termination. | Container limits contain resource use; the VM and unrelated test containers remain responsive; no stale containers, networks, or markers remain. |
| P1 | Runtime robustness | Run established upstream gVisor tests relevant to the selected platform and application APIs; repeat syscall and filesystem cases with concurrency. | No host/guest crash, panic, unexpected host access, or test hang; incompatibilities are documented with reproducible inputs. |
| P1 | Patch and artifact hygiene | Verify image digest and runtime artifact checksums; record versions; rerun a compact regression set after kernel, Docker, or gVisor updates. | Artifacts match recorded digests; updated versions pass the regression suite before being accepted. |
| P2 | Real agent workload and performance | Run representative coding/tool workloads with realistic file and network needs; repeat across multiple VM boots and longer trials. Measure startup, execution, pause/resume if relevant, and resource use. | Required tasks work under least privilege; overhead and compatibility gaps are documented with repeatable samples. |

The P0 cases are the recommended next test batch. P1 and P2 broaden confidence and should follow before any production decision. For any network-sensitive deployment, enforce egress restrictions at the network boundary in addition to the application proxy. For availability, retain host-level cgroup/resource limits; the gVisor project explicitly identifies these as part of the defense against resource exhaustion. [gVisor security model](https://gvisor.dev/docs/architecture_guide/security/)

## Decision criteria for the next review

Proceed to a broader pilot only if:

1. All P0 cases pass under the exact runtime and launch configuration proposed for the pilot.
2. Every negative control is detected, including host namespace, device, and mount-policy regressions.
3. No test reads or writes an unexposed host marker, reaches an unapproved endpoint, or changes host state.
4. Resource-limit cases stay within the VM's defined safety ceiling and clean up reliably.
5. Results are reproducible, versioned, and reviewed with all failures and limitations visible.

These criteria raise confidence in the tested deployment configuration; they do not prove the absence of vulnerabilities. A production decision should also include an explicit operational threat model, patch ownership, monitoring, incident response, and an independent security review.

## Evidence template

For each case, save:

- Test ID, date, operator, and threat-model assumption.
- VM/kernel, Docker, `runc`/`runsc`, profile, and image digest.
- Expected result and observed result, including exit code and relevant logs.
- Docker-inspected launch configuration and resource-limit settings.
- Pass/fail, cleanup result, and any deviation from the planned case.
- A minimal reproduction and issue reference for any unexpected behavior.


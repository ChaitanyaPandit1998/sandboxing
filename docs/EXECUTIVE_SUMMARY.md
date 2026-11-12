# Executive summary: gVisor sandbox POC

## Outcome

The POC demonstrated that gVisor (`runsc`) can run the same bounded workloads as Docker's standard `runc` runtime in our ARM64 Lima test environment. Both runtimes passed selected safety and cross-session checks, and the harness detected deliberately weakened configurations. The latest network testing also found a material gap: the demonstration proxy does not enforce TLS hostnames inside an allowed CONNECT tunnel. This remains a feasibility result, not evidence that strict egress policy is ready for production.

## Evidence

- Both runtimes passed **25 selected isolation and privilege checks**. The expanded proxy/parser suite passed **24 checks per runtime**, but strict hostname isolation failed the separate TLS tunnel observation described below.
- Follow-up outer-container probes passed under both runtimes: writes worked only in the intended workspace/tmp paths; writes through a symlink to `/etc` and to rootfs locations were blocked; and each session had a private process view. A second session could not see the first session's file, process environment, or a synthetic host marker.
- The expanded egress suite checked raw CONNECT/parser edge cases, host normalization, IP literals, alternate ports, DNS, and direct egress. In a separate tunnel probe, CONNECT to `example.com:443` carried TLS SNI and HTTP Host `example.org` and received `HTTP 200 OK` under both runtimes. The proxy validates CONNECT authority but cannot inspect the encrypted hostname. Thus strict hostname allowlisting is **not achieved**. The controlled DNS-rebinding sequence did reject a changed loopback answer.
- Negative controls detected **10/10 existing weakened scenarios** across both runtimes. An additional configuration-only suite detected privileged mode, host PID/network namespaces, device access, and writable bind mounts in all **10 runtime/scenario combinations**; those unsafe containers were never started.
- The seven-case syscall diagnostic completed under both runtimes and both seccomp profiles. Namespace, mount, and ptrace probes remain narrow invalid/denied calls, not a broad compatibility or escape test.
- Both runtimes passed nine selected everyday syscall/API probes, including relative `openat` file I/O, `memfd_create`/`mmap`, `eventfd`, `epoll`, Unix socketpair, child exec/wait, thread creation/join, `pidfd_open`, and `copy_file_range`.
- In a **20-trial benchmark on one VM**, `runsc` median workload time was **7.7% to 28.2% higher** than `runc`; end-to-end container time was **22.2% to 25.7% higher**.
- A follow-up found a large keep-alive difference under default TCP settings, but it fell to about **1%** when `TCP_NODELAY` was enabled on both ends. This loopback microbenchmark is sensitive to socket behavior and does not establish a general networking advantage.
- A small syscall matrix showed runtime-dependent behavior, but does not identify every enforcement layer.

## Recommendation

First replace or augment the demonstration proxy with a TLS-aware gateway or equivalent network policy, then rerun the tunnel bypass tests. Continue the remaining **P0 security-validation tests** in [SECURITY_VALIDATION_PLAN.md](SECURITY_VALIDATION_PLAN.md), including broader syscall, namespace, mount, and ptrace coverage. The syscall smokes are selected API checks, not the complete gVisor compatibility suite. For performance, repeat representative application-shaped session and network benchmarks across multiple VM boots.

**Decision boundary:** The POC supports continued evaluation; it does not yet support a production security claim or prove that `runsc` is more secure than `runc`. The checks above are targeted configuration probes; a broader adversarial security assessment and remaining planned cases are still outstanding. Evidence and scope are tracked in [AGENT_SESSION_VALIDATION_PLAN.md](AGENT_SESSION_VALIDATION_PLAN.md).

Detailed methodology and results are in [REPORT.md](REPORT.md); the full project overview is in [POC_SUMMARY.md](POC_SUMMARY.md). See the [runtime architecture](diagrams/architecture.svg), [egress path and TLS limitation](diagrams/network-architecture.svg), and [repository file flow](diagrams/file-flow.svg).

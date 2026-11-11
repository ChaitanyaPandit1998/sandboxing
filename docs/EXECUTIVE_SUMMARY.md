# Executive summary: gVisor sandbox POC

## Outcome

The POC demonstrated that gVisor (`runsc`) can run the same bounded workloads as Docker's standard `runc` runtime in our ARM64 Lima test environment. Both runtimes passed selected safety, cross-session isolation, and network-policy checks, and the test harness detected deliberately weakened configurations. This is a positive feasibility result and supports moving to a focused security-validation phase.

## Evidence

- Both runtimes passed **25 selected isolation and privilege checks** and **5 HTTPS allowlist checks**.
- Follow-up outer-container probes passed under both runtimes: writes worked only in the intended workspace/tmp paths; writes through a symlink to `/etc` and to rootfs locations were blocked; and each session had a private process view. A second session could not see the first session's file, process environment, or a synthetic host marker.
- The final egress suite passed **17/17 checks per runtime**, including redirecting from allowlisted `httpbin.org` to denied `example.org`, raw CONNECT authority/Host-header tricks, lookalike hosts, IPv4/IPv6 literals, alternate ports, plain HTTP, direct UDP DNS, and direct IPv4/IPv6 egress. A separate controlled DNS-rebinding sequence passed under both runtimes: the proxy allowed the initial public answer and rejected the subsequent loopback answer. These results validate this test proxy and network setup, not every possible protocol or bypass.
- Negative controls detected **10/10 existing weakened scenarios** across both runtimes. An additional configuration-only suite detected privileged mode, host PID/network namespaces, device access, and writable bind mounts in all **10 runtime/scenario combinations**; those unsafe containers were never started.
- The seven-case syscall diagnostic completed under both runtimes and both seccomp profiles. Namespace, mount, and ptrace probes remain narrow invalid/denied calls, not a broad compatibility or escape test.
- Both runtimes also passed selected everyday syscall/API probes: relative `openat` file I/O, `memfd_create`/`mmap`, `eventfd`, `epoll`, Unix socketpair, child exec/wait, and thread creation/join.
- In a **20-trial benchmark on one VM**, `runsc` median workload time was **7.7% to 28.2% higher** than `runc`; end-to-end container time was **22.2% to 25.7% higher**.
- A follow-up found a large keep-alive difference under default TCP settings, but it fell to about **1%** when `TCP_NODELAY` was enabled on both ends. This loopback microbenchmark is sensitive to socket behavior and does not establish a general networking advantage.
- A small syscall matrix showed runtime-dependent behavior, but does not identify every enforcement layer.

## Recommendation

Proceed with the remaining **P0 security-validation tests** in [SECURITY_VALIDATION_PLAN.md](SECURITY_VALIDATION_PLAN.md): broader protocol-specific bypass cases and syscall, namespace, mount, and ptrace coverage. The current syscall smokes are selected API checks, not the complete gVisor compatibility suite. For performance, repeat representative application-shaped network benchmarks across multiple VM boots.

**Decision boundary:** The POC supports continued evaluation; it does not yet support a production security claim or prove that `runsc` is more secure than `runc`. The checks above are targeted configuration probes; a broader adversarial security assessment and remaining planned cases are still outstanding. Evidence and scope are tracked in [AGENT_SESSION_VALIDATION_PLAN.md](AGENT_SESSION_VALIDATION_PLAN.md).

Detailed methodology and results are in [REPORT.md](REPORT.md); the full project overview is in [POC_SUMMARY.md](POC_SUMMARY.md).

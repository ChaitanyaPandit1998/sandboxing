# POC Requirements and Evidence Status

**Reviewed:** 2026-11-12
**Source:** requirements captured on the project whiteboard and evidence in this repository.
**Status key:** **Demonstrated** = evidence meets the stated requirement; **Partial** = some relevant cases were exercised, but the requirement is not fully met; **Not tested** = no direct evidence yet.

## Summary

| Group | Total | Demonstrated | Partial | Not tested |
|---|---:|---:|---:|---:|
| Functional requirements | 4 | 0 | 4 | 0 |
| Non-functional requirements | 3 | 0 | 2 | 1 |

These are status counts for the four functional and three non-functional top-level items. The policy requirement contains five separate controls, detailed below. **No top-level requirement is fully demonstrated yet.**

## Functional requirements

| ID | Requirement | Status | Evidence and remaining work |
|---|---|---|---|
| FR-1 | Support up to 20 concurrent sessions, starting with 5 | **Partial** | The cached-image sandbox benchmark passed 50/50 starts per runtime. The managed local worker also held five sessions, rejected a sixth, and passed a separate single-session authenticated persistence test. Full authenticated concurrent service readiness and 20-session scaling remain unverified. See [worker results](runbooks/MANAGED_WORKER.md) and [baseline readiness](reports/SESSION_READINESS_RESULTS.md). |
| FR-2 | Apply the required policy checks | **Partial** | The POC verifies selected configuration and network controls, but not the complete policy set. See the five subcontrols below. |
| FR-3 | Provide a dashboard for session and suspicious-activity monitoring | **Partial** | A [live local console](runbooks/LOCAL_CONSOLE.md) manages real worker create/list/inspect/stop state and lifecycle events. Login/attach use Mac Terminal handoff. Browser terminal relay, organization access, suspicious-activity detection, and alerts remain pending. |
| FR-4 | Add telemetry | **Partial** | Benchmark metrics, redacted gateway decisions, and local worker SQLite lifecycle events exist. Central session telemetry, organization actor attribution, monitoring, and suspicious-activity detection remain pending. |

### FR-2 policy subcontrols

| Control | Status | Evidence and remaining work |
|---|---|---|
| Allow approved websites | **Partial** | Basic allowlisted CONNECT behavior was tested. A TLS SNI/HTTP Host mismatch succeeded inside an allowed CONNECT tunnel, so strict hostname allowlisting is not achieved. |
| Block disallowed websites | **Partial** | Basic unlisted-host and direct-egress denial probes passed. The TLS tunnel result means the current proxy does not reliably block a different encrypted hostname inside an allowed tunnel. |
| Defend against prompt injection | **Not tested** | No prompt-injection threat cases, detection, mitigation, or recovery behavior have been evaluated. Runtime isolation alone is not a prompt-injection defense. |
| Deny access to critical filesystems | **Partial** | Read-only root, no host mounts, synthetic host-marker isolation, and selected sensitive-path write probes passed. A complete policy for critical paths and read attempts has not been defined or tested. |
| Require human approval where policy requires it | **Partial** | Synthetic egress requests were held for approval; approve and deny outcomes were observed. Requirement-specific approval rules, named human identity attribution, and authorization roles remain unverified. |

## Non-functional requirements

| ID | Requirement | Status | Evidence and remaining work |
|---|---|---|---|
| NFR-1 | p95 latency to start a new container/session is below 20 seconds | **Partial** | Baseline five-container starts measured p95 0.486s runc / 0.444s stable runsc. Five concurrent managed-worker create requests reached login-ready in 1.117–5.707s, including queueing. These are CLI/lower-level measurements; full authenticated service/attach p95 remains unmeasured. See [worker results](runbooks/MANAGED_WORKER.md). Resolve the whiteboard <20s versus agreed pilot <25s target before acceptance. |
| NFR-2 | `runc` and `runsc` benchmark difference is below 15% | **Partial; not consistently met** | In the 20-trial workload benchmark, `runsc` median was 7.7% slower for CPU, 15.0% for `/tmp` I/O, and 28.2% for fresh-connection HTTP. End-to-end container wall time was 22.2–25.7% higher. Keep-alive results were highly sensitive to TCP settings. The target is not met across all measured workloads. |
| NFR-3 | Container uptime is above 90% | **Not tested** | No sustained uptime/availability or soak test has been run. Short successful sessions do not measure uptime. Define the observation window and what counts as available before testing. |

## Evidence boundaries and next steps

- The benchmark compares selected synthetic workloads in one Lima VM. It does not measure production application latency or full session readiness.
- The security checks are targeted configuration probes, not a security certification. A passing probe does not establish that `runsc` is more secure than `runc`.
- Close the TLS hostname enforcement gap, define prompt-injection and critical-filesystem policies, then test those controls with bypass and negative cases.
- Run five-session and then 20-session startup/load tests. Record request-to-ready p50/p95, queue time, failure rate, CPU, memory, and cleanup separately.
- Run an uptime/soak test over an agreed period and report actual availability and recovery behavior.
- Resolve the whiteboard `<20s` latency target versus the agreed pilot `<25s` target before setting a release gate.

## Related documentation

- [POC summary](overview/POC_SUMMARY.md) and [detailed experiment report](reports/REPORT.md) contain runtime and policy evidence.
- [Executive summary](overview/EXECUTIVE_SUMMARY.md) gives the leadership-level result.
- [Platform roadmap](platform/PLATFORM_ROADMAP.md) and [session control-plane spec](platform/SESSION_CONTROL_PLANE_SPEC.md) describe proposed product work and the agreed pilot scope.
- [UI prototype notes](platform/UI_PROTOTYPE.md) explain which dashboard behavior is simulated.
- [Wardyn fit assessment](platform/WARDYN_FIT_ASSESSMENT.md) records the separate control-plane compatibility checks; those do not count as a POC concurrency, latency, or uptime benchmark.

The [strict HTTPS egress plan](security/TLS_GATEWAY.md#enforcement-design-and-remaining-acceptance) defines the gateway and acceptance cases; an initial candidate is implemented with 16 passing checks per runtime, while the full matrix and default-runner integration remain pending.

**Expiry/UI follow-up (2026-11-13):** New sessions receive the agreed one-hour deadline; legacy sessions remain unchanged. Twenty-two worker checks and thirteen API/background tests passed, including injected overdue-session cleanup and workspace retention. The UI displays deadlines and sweep health, and live Inspect/layout were reviewed. Resident cleanup now runs under a supervised VM user service independently of the Mac backend (11 isolated service checks and 14 API tests passed). Alerts, SSO, full authenticated concurrent readiness, VM restart validation and uptime remain pending.

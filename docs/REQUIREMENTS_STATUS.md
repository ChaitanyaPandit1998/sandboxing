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
| FR-1 | Support up to 20 concurrent sessions, starting with 5 | **Partial** | A cached-image five-session sandbox smoke passed 50/50 starts per runtime, with successful workspace writes and CLI startup. Full authenticated session/platform capacity and 20-session scaling remain unverified. See [readiness results](SESSION_READINESS_RESULTS.md). |
| FR-2 | Apply the required policy checks | **Partial** | The POC verifies selected configuration and network controls, but not the complete policy set. See the five subcontrols below. |
| FR-3 | Provide a dashboard for session and suspicious-activity monitoring | **Partial** | A static UI prototype and experiment/audit outputs exist. The prototype uses simulated data; there is no live session dashboard, alerting, or suspicious-activity detection. |
| FR-4 | Add telemetry | **Partial** | The benchmark records workload/container timings, environment metadata, and raw samples. Session lifecycle, policy-decision, and suspicious-activity telemetry are not implemented as a service. |

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
| NFR-1 | p95 latency to start a new container/session is below 20 seconds | **Partial** | Five concurrent cached-image sandbox starts measured p95 0.486s for runc and 0.444s for stable runsc, including a workspace write and CLI version command. Full request-to-session-ready p95 through a control plane, authentication and attach remain unmeasured. See [readiness results](SESSION_READINESS_RESULTS.md). The agreed first-pilot spec currently says below 25 seconds at five concurrent sessions; reconcile this with the stricter whiteboard target before acceptance. |
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

- [POC summary](POC_SUMMARY.md) and [detailed experiment report](REPORT.md) contain runtime and policy evidence.
- [Executive summary](EXECUTIVE_SUMMARY.md) gives the leadership-level result.
- [Platform roadmap](PLATFORM_ROADMAP.md) and [session control-plane spec](SESSION_CONTROL_PLANE_SPEC.md) describe proposed product work and the agreed pilot scope.
- [UI prototype notes](UI_PROTOTYPE.md) explain which dashboard behavior is simulated.
- [Wardyn fit assessment](WARDYN_FIT_ASSESSMENT.md) records the separate control-plane compatibility checks; those do not count as a POC concurrency, latency, or uptime benchmark.

The [strict HTTPS egress plan](EGRESS_ENFORCEMENT_PLAN.md) defines the gateway and acceptance cases; an initial candidate is implemented with 16 passing checks per runtime, while the full matrix and default-runner integration remain pending.

**TLS gateway candidate update (2026-11-12):** A separate TLS-terminating gateway passed 16 selected checks under each runtime, including the previously observed SNI mismatch and a decrypted HTTP Host mismatch. See [candidate results and remaining gates](TLS_GATEWAY_RESULTS.md). The default agent proxy is unchanged; full egress-policy acceptance remains open. A subsequent explicit HTTPS configuration completed three authenticated tasks without reconnect/error events; broader transport and failure testing remain open.

**Authenticated gateway follow-up (reviewed 2026-11-13):** Private ChatGPT login, one synthetic workspace-write task, incremental CLI events, cancellation, and cleanup passed. The initial run used fallback after WebSocket denials; the explicit HTTPS follow-up completed three tasks with zero error events. See [evidence and remaining checks](CODEX_TLS_AUTHENTICATED_RESULTS.md). This does not measure platform session-ready p95.

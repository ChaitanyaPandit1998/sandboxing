# POC Requirements and Evidence Status

**Reviewed:** 2026-11-13
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
| FR-1 | Support up to 20 concurrent sessions, starting with 5 | **Partial** | The cached-image sandbox benchmark passed 50/50 starts per runtime. The managed local worker also held five sessions, rejected a sixth, and passed a separate single-session authenticated persistence test. Five concurrent authenticated reply-only probes passed on one account (36.284–38.690s after login). Full service/attach readiness, distinct-user behavior and 20-session scaling remain unverified. See [worker results](runbooks/MANAGED_WORKER.md) and [baseline readiness](reports/SESSION_READINESS_RESULTS.md). |
| FR-2 | Apply the required policy checks | **Partial** | The POC verifies selected configuration and network controls, but not the complete policy set. See the five subcontrols below. |
| FR-3 | Provide a dashboard for session and suspicious-activity monitoring | **Partial** | A [live local console](runbooks/LOCAL_CONSOLE.md) manages real worker create/list/inspect/stop state and lifecycle events. Login/attach use Mac Terminal handoff. The UI now shows selected live policy checks and filterable drift/egress-denial/lifecycle review signals. Durable local event history and acknowledge/resolve/reopen alerts are implemented. Browser terminal relay, organization access, attack detection and central delivery remain pending. |
| FR-4 | Add telemetry | **Partial** | Live Docker agent CPU/memory/PIDs, bounded gateway decision counts, lifecycle events and recorded timing charts are exposed in the local console. A bounded durable lifecycle/security journal and local alert action trail are now available. Historical resource collection, central telemetry, organization actor attribution, attack detection and external delivery remain pending. |

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

**Expiry/UI follow-up (2026-11-13):** New sessions receive the agreed one-hour deadline; legacy sessions remain unchanged. Twenty-two worker checks and thirteen API/background tests passed, including injected overdue-session cleanup and workspace retention. The UI displays deadlines and sweep health, and live Inspect/layout were reviewed. Resident cleanup now runs under a supervised VM user service independently of the Mac backend (11 isolated service checks and 14 API tests passed). External alerts, SSO, full authenticated service/attach readiness and uptime remain pending; the later VM restart check is recorded below.


**Recovery follow-up (2026-11-13):** Nine actual VM stop/start checks passed with isolated synthetic resources; automatic service startup, overdue/lost-session cleanup and workspace retention were verified. Five new concurrent sessions reached login-ready in 0.788–4.259 seconds in one cached-image batch. Subsequent independent private sign-ins and five concurrent authenticated reply-only probes passed; post-login completion took 36.284–38.690s, excluding provisioning and manual login. Mac sleep recovery, sustained uptime, and statistically meaningful p95 readiness remain open; these observations do not close the top-level NFRs. [Recovery evidence](../results/vm-recovery-20261113/restart.json), [timings](../results/five-session-pilot-20261113/login-ready.json).


**Authenticated concurrency follow-up (2026-11-13):** [Five of five model probes passed](../results/five-session-pilot-20261113/authenticated.json) with zero recorded error events. This is a reply-only task in five sessions on one account, after manual login. It improves FR-1 evidence but does not close the 20-session requirement or the service-readiness p95/uptime gates. Median post-login reply completion was 37.648s; provisioning remains a separate measurement. Test sessions were stopped with workspace retained.


**Coding follow-up (2026-11-13):** One authenticated Node coding/tool task passed independent correctness checks and five generated tests. First message event: **4.233s**; first tool: **5.121s**; CLI completion: **22.099s**, excluding provisioning and login. One intermediate command failed before final success; its cause is unclassified. An initial Python task could not run because Python is absent from the image. This improves agent compatibility evidence but does not close any concurrency, latency-p95, critical-filesystem or uptime acceptance gate. [Evidence](../results/coding-task-20261113/summary.json).


**UI observability follow-up (2026-11-13):** Four local console sections now expose nine selected configuration checks, live agent resource snapshots, filterable review signals and default-deny hostname lookup. The live sample verified all nine checks, resource data and bounded egress decisions. Fourteen API tests and three sanitization/policy tests passed; browser behavior was reviewed. Live monitoring remains read-only and sampled; the later local durable journal/alert follow-up below adds a review workflow. Hostname history, a prompt-injection detector, policy editor and central alerts remain absent. FR-3/FR-4 remain partial. [Runbook](runbooks/LOCAL_CONSOLE.md#security-and-observability-views-2026-11-13).


**Durable alert/history follow-up (2026-11-13):** Resident collection now persists deduplicated lifecycle/security events, local alert state and actor-labeled action history. Real rejected-flow tests verified open → acknowledge → resolve → reopen, deduplication after collector restart and retained state after console restart. Browser controls and filters passed. Six journal, four sanitization/policy and 16 API tests passed, along with 11 isolated service checks. Retention is bounded and traffic sampling can miss events; actor attribution remains a trusted local label. FR-3/FR-4 remain partial pending detection coverage, external delivery, centralized telemetry and organization identity. [Runbook](runbooks/LOCAL_CONSOLE.md#durable-history-and-local-alerts-2026-11-13), [evidence](../results/security-history-20261113/live-workflow.json).

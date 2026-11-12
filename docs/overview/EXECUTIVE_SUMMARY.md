# Executive summary: sandbox POC

## Outcome

The POC demonstrates authenticated Codex tasks through a TLS gateway and a managed local worker with a persistent pilot workspace, temporary login homes, and selected cleanup/recovery controls. It supports continued single-user evaluation. The browser UI remains a static prototype; HTTP service integration, organization identity, background expiry, and authenticated concurrent readiness are unfinished.

## Evidence

- The [managed worker](../runbooks/MANAGED_WORKER.md) passed 17 synthetic checks and one authenticated workspace-write/stop/replacement check. The workspace file survived; login state did not. Five simultaneous create requests reached login-ready in 1.117–5.707s, including queueing. This is not authenticated session-ready p95.
- The [TLS gateway candidate](../security/TLS_GATEWAY.md) passed 16 selected checks per runtime, including the original TLS SNI bypass and encrypted HTTP Host mismatch. The original opaque CONNECT proxy remains limited. Full strict-egress acceptance is still open.
- The [explicit HTTPS Codex configuration](../runbooks/CODEX_TLS.md#explicit-https-configuration-and-validation) completed three authenticated tasks with zero reconnect/error events; cancellation took 0.396s. Additional denied CONNECT attempts remain unattributed.
- The [synthetic failure suite](../reports/STREAM_FAILURE_RESULTS.md) passed 11 checks per runtime for streaming, truncation, stalls, cancellation, upstream errors, and gateway restart/resume. It uses a local fixture; it does not establish authenticated Codex recovery or uptime.
- Archived runtime experiments passed selected boundary and negative-control checks. In the [20-trial benchmark](../reports/REPORT.md), runsc median workload time was 7.7–28.2% higher than runc and total container time 22.2–25.7% higher. Keep-alive results were sensitive to TCP settings; they do not establish a general networking advantage.

All four functional requirements and two of three non-functional requirements remain **partial**; uptime is unmeasured. See the [requirements matrix](../REQUIREMENTS_STATUS.md) for evidence, acceptance gaps, and the unresolved <20s versus <25s readiness target.

## Next decisions

Validate interactive attach, finish the control-plane/Wardyn integration decision, connect the worker to the service and UI, and add background expiry/reconciliation. Then measure full authenticated five-session readiness and sustained uptime, and complete the remaining [security](../validation/SECURITY_VALIDATION_PLAN.md) and [agent validation](../validation/AGENT_SESSION_VALIDATION_PLAN.md) gates. Selected probes do not establish production readiness or prove runsc more secure than runc.

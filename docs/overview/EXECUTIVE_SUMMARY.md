# Executive summary: sandbox POC

## Outcome

The POC demonstrates authenticated Codex tasks through a TLS gateway and a managed local worker with a persistent pilot workspace, temporary login homes, and selected cleanup/recovery controls. A [live local console](../runbooks/LOCAL_CONSOLE.md) now supports create/list/inspect/stop and events through a loopback API. The console also exposes selected live policy checks, resource telemetry, review signals, durable local history/alert acknowledgement and resolution, and read-only allowed/blocked-site lookup. Login and interactive Codex use Mac Terminal handoff. Five concurrent authenticated reply-only probes passed; organization identity, browser terminal relay and full service/attach readiness remain unfinished. New sessions now receive a one-hour deadline, with supervised cleanup polling inside the VM independently of the Mac backend.

## Evidence

- The [managed worker](../runbooks/MANAGED_WORKER.md) passed 17 synthetic checks and one authenticated workspace-write/stop/replacement check. The workspace file survived; login state did not. Five simultaneous create requests reached login-ready in 1.117–5.707s, including queueing. This is not authenticated session-ready p95.
- The [TLS gateway candidate](../security/TLS_GATEWAY.md) passed 16 selected checks per runtime, including the original TLS SNI bypass and encrypted HTTP Host mismatch. The original opaque CONNECT proxy remains limited. Full strict-egress acceptance is still open.
- The [explicit HTTPS Codex configuration](../runbooks/CODEX_TLS.md#explicit-https-configuration-and-validation) completed three authenticated tasks with zero reconnect/error events; cancellation took 0.396s. Additional denied CONNECT attempts remain unattributed.
- The [synthetic failure suite](../reports/STREAM_FAILURE_RESULTS.md) passed 11 checks per runtime for streaming, truncation, stalls, cancellation, upstream errors, and gateway restart/resume. It uses a local fixture; it does not establish authenticated Codex recovery or uptime.
- Archived runtime experiments passed selected boundary and negative-control checks. In the [20-trial benchmark](../reports/REPORT.md), runsc median workload time was 7.7–28.2% higher than runc and total container time 22.2–25.7% higher. Keep-alive results were sensitive to TCP settings; they do not establish a general networking advantage.

All four functional requirements and two of three non-functional requirements remain **partial**; uptime is unmeasured. See the [requirements matrix](../REQUIREMENTS_STATUS.md) for evidence, acceptance gaps, and the unresolved <20s versus <25s readiness target.

- A new five-session batch reached login-ready in **0.788–4.259s**. After private sign-in, **5/5 concurrent model probes passed**, with zero recorded errors and completed replies in **36.284–38.690s**. This uses one account and excludes manual login; it does not establish a reliable p95 or uptime. The test sessions were stopped with workspace retained. [Evidence](../../results/five-session-pilot-20261113/summary.json).

- A real Node coding task created files and passed **five generated tests plus independent correctness checks**. The first message arrived at **4.23s**, first tool at **5.12s**, and CLI completion at **22.10s**, after login. One intermediate tool command failed before final success. An earlier Python attempt exposed that Python is missing from the image. These are single-task observations, not p95 acceptance. [Evidence](../../results/coding-task-20261113/summary.json).

## Next decisions

Validate interactive attach, finish the control-plane/Wardyn integration decision, connect the worker to the service and UI, and extend the successful single VM-restart check to suspension and sustained recovery testing. Then measure repeated full authenticated service/attach readiness and sustained uptime, and complete the remaining [security](../validation/SECURITY_VALIDATION_PLAN.md) and [agent validation](../validation/AGENT_SESSION_VALIDATION_PLAN.md) gates. Selected probes do not establish production readiness or prove runsc more secure than runc.

# Authenticated Codex through the TLS gateway

**Reviewed:** 2026-11-13. Evidence is stored under the run identifier `codex-tls-authenticated-20261112`.

## Results

| Check | Observed result |
|---|---|
| Private device login | Login status confirmed ChatGPT authentication inside the temporary container. |
| Workspace task | Codex created `tls-smoke.txt` containing the expected synthetic marker; CLI exit code 0. |
| Incremental CLI events | Thread, turn, tool execution, and completion events arrived before process exit. This does not establish token-level or packet-level streaming behavior. |
| Total task duration | 16.083 seconds, including transport retries and model/tool work. This is one task sample, not session-ready p95. |
| WebSocket transport | Repeated attempts received 403 because the gateway refuses Upgrade requests. The task subsequently succeeded over fallback transport; WebSocket compatibility is unresolved. |
| Cancellation | SIGINT was sent after the synthetic workspace command started. Codex exited with code 1 after 0.379 seconds; the post-cancellation marker was absent. The nonzero exit is expected for this interrupted task. |
| Orphaned command | A post-cancellation check found zero remaining `sleep 60` processes. |
| Gateway logging | All 121 observed entries matched the four-field redacted policy schema. No unexpected log lines were observed. This verifies this run's output, not every possible failure/logging path. |
| Session cleanup | Codex logout succeeded. Owned session/gateway containers, networks, CA material, and memory-backed credentials/workspace were removed. |

The tested runtime was `runsc-stable-20261109`, with Codex CLI 0.167.1 and agent image ID `sha256:1c699e85c4765335983513403bc9edb812ffcc88dab0f9132274406079fdee5a`. Codex used `--no-daemon`, `workspace-write`, and a fixed synthetic prompt. No credential files were read or exported. The Codex container used Docker's `none` log driver; interactive login stayed in the user's terminal. Saved evidence contains selected event types/timings and marker results, not full model output.

Evidence: [task result](../results/codex-tls-authenticated-20261112/workspace-smoke.json), [cancellation](../results/codex-tls-authenticated-20261112/cancellation.json), [process check](../results/codex-tls-authenticated-20261112/post-cancel-processes.json), [summary](../results/codex-tls-authenticated-20261112/summary.json), and [redacted gateway decisions](../results/codex-tls-authenticated-20261112/gateway-decisions.jsonl).

## Remaining work

1. **Focused follow-up completed:** the [explicit HTTPS provider](CODEX_HTTPS_TRANSPORT.md) completed three authenticated workspace tasks without reconnect/error events and passed cancellation. The gateway still denies Upgrade. Broader transport/error tests remain open.
2. Test streaming/cancellation over repeated tasks, provider errors, and interrupted network connections. The current evidence is one successful task and one cancellation.
3. Complete controlled DNS-rebinding, invalid-upstream-certificate, redirect/reuse, ECH, and alternate-protocol checks from the [gateway plan](EGRESS_ENFORCEMENT_PLAN.md).
4. Integrate the candidate into the selected control plane, then measure full request-to-ready and attach latency at five authenticated sessions. This result does not validate Wardyn's credential integration, workspace persistence, 20-user scaling, or uptime.

Reproduction and private sign-in are described in [the Codex TLS session runbook](CODEX_TLS_SESSION.md). A new run requires fresh sign-in because the completed session was removed.

A follow-up check of `codex features list` in the same uncredentialed image reports `responses_websockets` and `responses_websockets_v2` as **removed**, both false. Do not assume those old feature switches provide a supported way to force HTTPS in this CLI version. `app_server_websocket_compression` concerns a different transport and is not a solution to the observed provider retries.

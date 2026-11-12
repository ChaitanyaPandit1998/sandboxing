# Codex login through the TLS gateway

**Status (reviewed 2026-11-13):** the first authenticated task succeeded after WebSocket denials and fallback. A subsequent [explicit HTTPS transport run](CODEX_TLS.md#explicit-https-configuration-and-validation) passed three authenticated workspace tasks with zero error events, cancellation, and live hostname-policy checks. Both temporary sessions were logged out and removed. Start a new session and complete private sign-in before using these commands again.

The [official authentication documentation](https://learn.chatgpt.com/docs/auth#custom-ca-bundles) describes `CODEX_CA_CERTIFICATE` and the `SSL_CERT_FILE` fallback. Both point to the public test CA in this session; `NODE_EXTRA_CA_CERTS` also supports the preflight client. Certificate verification remains enabled. No CA is installed on the Mac.

## Prepare inside the disposable VM

Copy `tls_gateway.py` and `scripts/run_codex_tls_session.sh` into the same repository layout in the VM. Then run:

```bash
bash scripts/run_codex_tls_session.sh start
bash scripts/run_codex_tls_session.sh status
```

The runner uses fixed, ownership-labelled resources prefixed `poc-codex-tls-` and refuses to replace existing containers/networks. It starts the digest-pinned mitmproxy gateway and the cached Codex image, restricts destinations to `auth.openai.com`, `chatgpt.com`, and `api.openai.com`, and gives the session only an internal network. The container has a read-only root and temporary writable home/workspace/tmp filesystems. Codex container Docker logging is disabled; interactive login stays in the user's terminal. The gateway's private CA remains in gateway tmpfs. The only trust material mounted into the session is the public certificate.

The runner now writes the explicit HTTPS provider configuration into the temporary Codex home. See [configuration and validation status](CODEX_TLS.md#explicit-https-configuration-and-validation). It preserves the gateway's Upgrade denial and hostname checks.

## Private login from Mac Terminal

```bash
limactl shell gvisor-poc -- docker exec -it poc-codex-tls-session codex login --device-auth
```

Complete the browser flow privately. Do not paste login codes, auth files, or tokens into chat. After login, the operator can check the authentication method without reading credential files, then run a fixed harmless workspace-write task, inspect completion/streaming and cancellation, and verify redacted gateway events. Do not copy existing personal authentication material into the session.

## Stop

After the authenticated checks, run this inside the VM:

```bash
bash scripts/run_codex_tls_session.sh stop
```

For the guest copy staged during this test, the Mac command is:

```bash
limactl shell gvisor-poc -- bash /tmp/poc-codex-tls-src/scripts/run_codex_tls_session.sh stop
```

Stopping deletes the memory-backed login home and workspace, gateway CA, and owned networks/containers. This test does not implement the planned persistent workspace or a session-management API. Restarting the session requires private sign-in again.

## Explicit HTTPS configuration and validation

**Status (2026-11-13):** private ChatGPT login, three authenticated workspace tasks, cancellation, and live hostname-policy probes passed with the explicit HTTPS configuration. No reconnect/error events were observed in those tasks or cancellation. The session was logged out and removed. This is a focused compatibility result, not platform readiness or an uptime measurement.

The earlier authenticated run succeeded after WebSocket denials and fallback. The removed `responses_websockets` feature switches do not solve this. The [official configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference) documents the provider setting `model_providers.<id>.supports_websockets`; the [official transport example](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations) describes `supports_websockets=false` selecting HTTP for that example. Those documents establish a configuration candidate; the exact cached CLI and ChatGPT-account path still require live validation.

The temporary session runner now writes this non-secret configuration into its memory-backed Codex home:

```toml
model_provider = "poc_https"

[model_providers.poc_https]
name = "OpenAI HTTPS through POC gateway"
base_url = "https://chatgpt.com/backend-api/codex"
wire_api = "responses"
requires_openai_auth = true
supports_websockets = false
```

This preserves private ChatGPT device login and the existing exact-host TLS gateway. It does not enable Upgrade, HTTP/2, raw TCP, or insecure certificate verification. The model is not overridden. The explicit backend URL is test configuration, not a claim that arbitrary provider endpoints are approved.

After fresh private sign-in, repeat the fixed workspace task and cancellation check. Record reconnect errors, incremental events, exit/marker outcomes, and redacted gateway decisions. Compare with the prior retrying sample without claiming a latency improvement from one run. Treat configuration rejection, account incompatibility, or continued WebSocket attempts as a failed candidate and record the actual error before choosing another approach.

### Live validation

The cached CLI first accepted the configuration with `codex exec --strict-config`. An unauthenticated request reached the HTTPS backend and returned 401, as expected. `--strict-config` is supported on `exec`, but not `login`, in this version. The user then completed private device login in the new memory-backed home.

| Check | Result |
|---|---|
| Authenticated workspace tasks | 3/3 passed; each wrote its exact synthetic marker and exited 0. |
| Task durations | 11.362s, 7.584s, 8.626s, including model/tool work. |
| Transport/reconnect errors | Zero error events across all three tasks and the cancellation run. |
| Incremental CLI events | Observed thread, turn, agent/tool, and completion events before process exit; not a packet-level streaming test. |
| Cancellation | Interrupted after the command started; exit code 1 after 0.396s, no post-cancel marker, zero remaining `sleep 60` processes. |
| Live gateway checks | Approved ChatGPT HTTPS returned 200; mismatched SNI, encrypted HTTP Host, and unlisted CONNECT each returned 403. |
| Logs | All 193 observed entries matched the redacted four-field schema; zero unexpected lines. |
| Cleanup | Logout succeeded; owned containers, networks, private CA and temporary login home were removed. |

There were 23 CONNECT-authority denials and two hostname-match denials in the captured gateway log. The deliberate live probes account for one CONNECT-authority denial and both hostname-match denials. The other 22 CONNECT-authority denials cannot be attributed from this intentionally redacted schema; do not assume all background network activity succeeded. The allowlist was not widened. These denials caused no observed task errors, but their cause remains an operational follow-up.

The exact runtime was `runsc-stable-20261109` and the agent image was the same Codex 0.167.1 image as the prior test. Evidence: [summary](../../results/codex-https-authenticated-20261113/summary.json), [task events](../../results/codex-https-authenticated-20261113/workspace-tasks.json), [cancellation](../../results/codex-https-authenticated-20261113/cancellation.json), [live policy probes](../../results/codex-https-authenticated-20261113/live-policy.json), and [redacted gateway events](../../results/codex-https-authenticated-20261113/gateway-decisions.jsonl).

Compared with the first fallback run, the observed WebSocket retries are eliminated in this three-task sample. Model workload variability and the small sample prevent a general latency or p95 claim. Next complete network/error/stream interruption tests, classify denied background traffic without exposing sensitive destinations, and validate the configuration through the selected control plane before promotion.

The [synthetic stream-failure follow-up](../reports/STREAM_FAILURE_RESULTS.md) subsequently passed 11 checks per runtime for progressive delivery, incomplete streams, stalls, cancellation, upstream errors, and gateway process restart/pause. These use a local fixture and test client; authenticated Codex/provider fault recovery is still unverified.

## Initial authenticated fallback test

**Reviewed:** 2026-11-13. Evidence is stored under the run identifier `codex-tls-authenticated-20261112`.

### Results

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

Evidence: [task result](../../results/codex-tls-authenticated-20261112/workspace-smoke.json), [cancellation](../../results/codex-tls-authenticated-20261112/cancellation.json), [process check](../../results/codex-tls-authenticated-20261112/post-cancel-processes.json), [summary](../../results/codex-tls-authenticated-20261112/summary.json), and [redacted gateway decisions](../../results/codex-tls-authenticated-20261112/gateway-decisions.jsonl).

### Remaining work

1. **Focused follow-up completed:** the [explicit HTTPS provider](CODEX_TLS.md#explicit-https-configuration-and-validation) completed three authenticated workspace tasks without reconnect/error events and passed cancellation. The gateway still denies Upgrade. Broader transport/error tests remain open.
2. Test streaming/cancellation over repeated tasks, provider errors, and interrupted network connections. The current evidence is one successful task and one cancellation.
3. Complete controlled DNS-rebinding, invalid-upstream-certificate, redirect/reuse, ECH, and alternate-protocol checks from the [gateway plan](../security/TLS_GATEWAY.md#enforcement-design-and-remaining-acceptance).
4. Integrate the candidate into the selected control plane, then measure full request-to-ready and attach latency at five authenticated sessions. This result does not validate Wardyn's credential integration, workspace persistence, 20-user scaling, or uptime.

Reproduction and private sign-in are described in [the Codex TLS session runbook](CODEX_TLS.md). A new run requires fresh sign-in because the completed session was removed.

A follow-up check of `codex features list` in the same uncredentialed image reports `responses_websockets` and `responses_websockets_v2` as **removed**, both false. Do not assume those old feature switches provide a supported way to force HTTPS in this CLI version. `app_server_websocket_compression` concerns a different transport and is not a solution to the observed provider retries.

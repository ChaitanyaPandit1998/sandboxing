# Explicit HTTPS transport candidate

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

## Live validation

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

The exact runtime was `runsc-stable-20261109` and the agent image was the same Codex 0.167.1 image as the prior test. Evidence: [summary](../results/codex-https-authenticated-20261113/summary.json), [task events](../results/codex-https-authenticated-20261113/workspace-tasks.json), [cancellation](../results/codex-https-authenticated-20261113/cancellation.json), [live policy probes](../results/codex-https-authenticated-20261113/live-policy.json), and [redacted gateway events](../results/codex-https-authenticated-20261113/gateway-decisions.jsonl).

Compared with the first fallback run, the observed WebSocket retries are eliminated in this three-task sample. Model workload variability and the small sample prevent a general latency or p95 claim. Next complete network/error/stream interruption tests, classify denied background traffic without exposing sensitive destinations, and validate the configuration through the selected control plane before promotion.

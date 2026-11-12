# Development log

Changes are recorded newest first. All timestamps use **Asia/Kolkata (IST, UTC+05:30)**.

Historical commit timestamps below are exact Git **author timestamps**, not test execution or push times. Entries marked **date only** have no independently recorded wall-clock execution time; no time has been invented. Entries without an explicit SHA may refer to the consolidation commit that contains them; use Git history for its exact ID. Relative test timings measure durations, not time of day.





## 2026-11-13T01:41:44+05:30 — Commit console, expiry and resident cleanup

- **Scope:** Consolidated the live local console, one-hour session expiry, supervised VM reconciliation, runbooks and sanitized validation evidence for commit and push at the user's request. Earlier uncommitted-state notes describe their batch-time state.
- **Checks:** Reviewed tracked/untracked paths, Git whitespace validation and targeted credential-pattern scan; no credentials found. Existing evidence records 22 worker checks, 11 resident service checks and 14 API tests passing. No new runtime tests were needed for this commit-only operation.
- **Next:** Validate VM restart/suspend recovery, authenticated interactive attach and five-session readiness. Git history and the remote record the resulting commit/push status.


## 2026-11-13T01:39:25+05:30 — Supervised resident VM cleanup

- **Changed:** Installed/enabled a systemd user reconciler in the Lima VM, checking every 30 seconds independently of the Mac console. Added private atomic health metadata, sanitized worker health action, and console resident/fallback status. Existing lingering was already enabled. Updated current runbooks, requirements and platform summaries.
- **Validation:** Eleven isolated service checks passed: injected expiry without console activity, supervised restart after SIGKILL, test-only Docker connection failure/recovery, and workspace retention. Fourteen API tests passed including live synthetic lifecycle/background expiry and resident-health response; JS/shell syntax passed. Live console reported active, fresh resident health with successful sweep; browser review confirmed the healthy indicator and zero active sessions. [Evidence](results/resident-cleanup-20261113/).
- **Failures/corrections:** Initial namespace-hardened user unit failed at CAPABILITIES with EPERM; revised to supported user-service controls without changing global kernel/AppArmor or container policy. Initial API test needed socket escalation; subsequent live test exposed a health-update assertion race, fixed by waiting for both expiry and completed sweep. Evidence copy initially used a missing destination and was retried successfully.
- **Limits:** Worker is trusted and has Docker access; no filesystem namespace sandbox on this unit. No reboot/suspend, one-hour soak, clock-jump or uptime SLO validation. The previously referenced session was already stopped with operator reason before installation; no user session was stopped by this batch. Synthetic test resources were cleaned; retained pilot workspace unchanged.
- **Status / next:** Changes are uncommitted and unpushed. Next validate VM restart/suspend recovery and authenticated interactive attach, then five-session authenticated readiness against the agreed p95 target.


## 2026-11-13T01:22:34+05:30 — One-hour expiry, background cleanup and UI review

- **Changed:** Added persisted session deadlines and stop reasons with a locked SQLite migration. The user selected a one-hour default for new sessions. Idempotent retries do not extend expiry; legacy sessions keep null deadlines. The console reconciles every 30 seconds while its backend is running, and displays deadlines and cleanup health.
- **Validation:** Twenty-two worker checks and thirteen API/background tests passed. A synthetic past deadline triggered cleanup without a browser request; workspace data survived. The real existing active session remained ready with no deadline. Native browser review verified live rows, Inspect/close, event display, expiry and sweep health; a responsive fix kept all action buttons visible.
- **Limits:** Tests injected an elapsed timestamp, not a one-hour soak. Backend/VM downtime or Mac sleep pauses cleanup; this is not hard expiry or an uptime SLO. Existing user sessions were not stopped or retroactively timed out. Browser create/stop was not clicked against the user's active session; those actions have HTTP integration coverage.
- **Evidence:** [Worker](results/session-expiry-20261113/worker.json), [background API](results/session-expiry-20261113/api-background.json), [live/browser review](results/session-expiry-20261113/live-review.json), [console runbook](docs/runbooks/LOCAL_CONSOLE.md).
- **State:** Uncommitted. The owned loopback backend was restarted to enable the sweeper and remains running for the pilot.
- **Next:** Move expiry enforcement to a resident worker service, validate authenticated interactive attach and concurrent readiness, and complete organization identity/browser relay gates.

## 2026-11-13T01:06:37+05:30 — Real local console and managed terminal handoff

- **Changed:** Added `serve_session_console.py` and `ui/console/` with real worker create/list/inspect/stop/events, fixed policy/idempotency, explicit unavailable states, and private login/attach command handoff. Retained the static prototype separately and ignored generated Python bytecode.
- **Boundary:** Loopback-only binding; Host/Origin/Fetch Metadata checks, HttpOnly/SameSite browser session and CSRF checks, bounded JSON, fixed actions, sanitized errors, and limited static routes. This trusts local processes/operators and is not organization authentication or browser terminal relay.
- **Validation:** Twelve tests passed (11 HTTP/static boundary tests plus a live synthetic worker lifecycle with eight assertions). Live assets, JavaScript syntax, and DOM IDs were checked. A native attach displayed Codex 0.167.1/sign-in menu and exited on Ctrl+C. Diagnostic sessions were stopped; synthetic test volumes were removed and the pilot workspace retained.
- **Failure / limits:** The initial automated pseudo-terminal screen detector did not recognize the UI; native terminal validation confirmed startup. No graphical browser layout/click test was performed. Authenticated interactive attach, browser relay, expiry, multi-user authorization, and full readiness SLO remain pending. Closing the page/server does not stop sessions.
- **Evidence:** [Console runbook](docs/runbooks/LOCAL_CONSOLE.md), [API results](results/session-console-20261113/api-checks.json), [terminal check](results/session-console-20261113/terminal-attach.json), [assets](results/session-console-20261113/assets.json).
- **State:** Uncommitted; local preview running for operator handoff.
- **Next:** Review the browser workflow, implement expiry/background reconciliation and the eventual authorized terminal/control-plane path.

## 2026-11-13T00:47:02+05:30 — Consolidate documentation and record completed worker validation

- **Changed:** Added `docs/README.md` as the navigation index; grouped content into overview, runbooks, security, reports, validation, platform, and diagrams. Merged three Codex TLS/login/transport files into one guide and gateway design/results into one security document. Removed superseded originals and duplicate dated progress paragraphs, preserving unique findings and raw evidence.
- **Updated:** Rebased documentation links, pinned the Wardyn source links, updated prototype links and its local preview instructions, and refreshed the executive summary. Current status belongs in the requirements matrix; this file retains the chronology.
- **Validation:** Checked local Markdown targets/anchors, HTML documentation links, SVG XML, Git diff formatting, source/evidence fingerprints, and the existing 17 worker / 22 fault-check results. No implementation change or additional model call was needed for this documentation batch.
- **Included work:** This consolidation commit also records the previously uncommitted managed worker, synthetic fault suite, evidence, and devlog guidance described below. Entries without a SHA reference the commit containing this log update, avoiding a fabricated self-referential commit hash.
- **State:** Included in the documentation consolidation commit; actual push completion is verified and reported separately.
- **Next:** Validate interactive attach, complete the service/control-plane integration decision, then connect the UI backend and add expiry/reconciliation services.

## 2026-11-13T00:40:02+05:30 — Start the development log

- **Changed:** Created this history from Git records and saved evidence, linked it from the README, and added repository guidance to maintain it for subsequent work.
- **Validation:** Historical commit IDs/times checked against Git; current results checked against the linked JSON evidence. This documentation change does not add a runtime test.
- **State:** Included in the documentation consolidation commit described above.
- **Next:** Validate managed interactive attach, choose/connect the control plane and UI backend, then add automatic expiry and authenticated concurrent readiness measurement.

## 2026-11-13 — Managed local worker (date only; included in consolidation commit)

- **Changed:** Added [`manage_codex_session.py`](scripts/manage_codex_session.py) with create/list/inspect/login/attach/stop/reconcile/events commands, private SQLite metadata, fixed runtime/image policy, ownership checks, idempotency, and a five-session quota. Integrated the TLS gateway and explicit HTTPS provider.
- **Storage:** Added a persistent Docker workspace for the local pilot. Session homes and CA keys remain temporary; stop retains the workspace. Sessions for this one pilot intentionally share the volume.
- **Successful:** [17 synthetic integration checks](results/managed-worker-20261113/checks.json) passed. Five simultaneous create requests reached **login-ready** in 1.117–5.707 seconds. A separate [authenticated task](results/managed-worker-20261113/authenticated.json) completed in 9.871 seconds with zero error events; its file survived stop/replacement and the replacement had no login state.
- **Limits / pending:** Login was exercised through the managed terminal command. Interactive model attach is implemented but still awaits manual validation. There is no HTTP API, browser terminal, SSO, background expiry/reconciler, or authenticated five-session p95 measurement. Synthetic test resources were removed; the real pilot workspace remains retained.
- **Details:** [Managed worker](docs/runbooks/MANAGED_WORKER.md), [source/environment fingerprints](results/managed-worker-20261113/environment.json).

## 2026-11-13 — Stream and gateway failure checks (date only; included in consolidation commit)

- **Changed:** Added a local TLS/SSE fixture and [`run_stream_failure_smoke.py`](scripts/run_stream_failure_smoke.py) for progressive delivery, truncation, idle timeout, cancellation, upstream reset/503, gateway kill/restart, and pause/resume.
- **Successful:** [11 checks per runtime](results/stream-failures-20261113/summary.json), 22 total, passed under `runc` and stable `runsc`. New requests recovered after the test supervisor restarted or resumed the gateway. Temporary resources and private keys were removed.
- **Limits / finding:** A truncated stream could end without an HTTP exception while lacking its application completion marker. HTTP 200 alone does not prove task completion. Test-only loopback routing replaces production DNS/public-IP routing; this is not authenticated Codex recovery, worker failover, or uptime evidence.
- **Details:** [Stream-failure report](docs/reports/STREAM_FAILURE_RESULTS.md).

## 2026-11-13T00:17:12+05:30 — Authenticated Codex HTTPS transport and cancellation

- **Commit:** [`4e1fd32`](https://github.com/ChaitanyaPandit1998/sandboxing/commit/4e1fd32) — committed and pushed to `main`.
- **Changed:** Added the isolated Codex session runner, private device-login runbook, authenticated evidence, and explicit `poc_https` provider with `supports_websockets=false`.
- **Successful:** Three authenticated workspace tasks passed without reconnect/error events; durations were 11.362, 7.584, and 8.626 seconds. Cancellation completed in 0.396 seconds with no leftover command. Live hostname mismatch probes remained denied. [Evidence](results/codex-https-authenticated-20261113/summary.json).
- **Failure addressed:** The initial [authenticated run](results/codex-tls-authenticated-20261112/workspace-smoke.json) encountered WebSocket 403/retries before fallback succeeded. Removed feature switches were not a supported fix; explicit provider configuration eliminated the observed retries in the follow-up sample.
- **Remaining:** Additional blocked CONNECT attempts could not be attributed from redacted logs. The sample does not establish latency p95 or production reliability. Sessions were logged out and removed.
- **Details:** [HTTPS transport](docs/runbooks/CODEX_TLS.md#explicit-https-configuration-and-validation), [initial authenticated results](docs/runbooks/CODEX_TLS.md#initial-authenticated-fallback-test).

## 2026-11-12T21:24:16+05:30 — TLS gateway candidate and five-session baseline

- **Commit:** [`67b64d3`](https://github.com/ChaitanyaPandit1998/sandboxing/commit/67b64d3) — committed and pushed to `main`.
- **Changed:** Added the mitmproxy-based TLS gateway, digest-pinned dependency, exact CONNECT/SNI/HTTP Host checks, public-address routing validation, and a cached-image readiness runner.
- **Successful:** [16 gateway checks per runtime](docs/security/TLS_GATEWAY.md) passed, including the observed SNI bypass and encrypted HTTP Host mismatch. [100 baseline sandbox starts](docs/reports/SESSION_READINESS_RESULTS.md) passed across ten rounds of five starts per runtime; p95 was 0.486s for `runc` and 0.444s for stable `runsc`.
- **Failures addressed:** The container image entrypoint expected root, so the runner invoked mitmdump directly as non-root. The public CA had to be exported from tmpfs through `docker exec`. The provider positive control used `/v1/models` and required 401 rather than accepting a response from `/`.
- **Limits:** These were uncredentialed gateway and cached sandbox checks, not full authenticated session readiness. The original opaque CONNECT proxy remains unchanged and limited.

## 2026-11-12T19:30:02+05:30 — Requirements, platform contract, and UI prototype

- **Commit:** [`e3e6da8`](https://github.com/ChaitanyaPandit1998/sandboxing/commit/e3e6da8) — committed and pushed to `main`.
- **Changed:** Added the whiteboard [requirements matrix](docs/REQUIREMENTS_STATUS.md), session control-plane draft, single-user/five-session pilot decisions, persistent-workspace goal, and static dashboard prototype. Updated report and roadmap links/statuses.
- **Validation / limits:** Documentation links and diff formatting were checked. UI lifecycle actions and metrics are simulated. The whiteboard p95 target (<20s) and accepted pilot target (<25s) were explicitly recorded as a decision to resolve.

## 2026-11-12T16:51:11+05:30 — Findings and TLS hostname gap

- **Commit:** [`681547f`](https://github.com/ChaitanyaPandit1998/sandboxing/commit/681547f).
- **Changed:** Updated reports, summaries, and architecture documentation with the tested boundaries and material egress limitation.
- **Finding:** The original proxy allowed TLS SNI/HTTP Host `example.org` through a CONNECT authorized for `example.com`. Earlier allowlist pass counts did not establish strict hostname isolation. Preserve this historical result alongside the later gateway candidate evidence.

## 2026-11-12T14:46:50+05:30 — Wardyn attach and expiry evaluation

- **Commit:** [`5e203e7`](https://github.com/ChaitanyaPandit1998/sandboxing/commit/5e203e7).
- **Successful:** Recorded relay attach/detach and lease-end behavior in a disposable Wardyn stack.
- **Limits / failure:** Default grace retained the stopped container; zero-grace cleanup/recovery remained open. A restart attempt failed after an ephemeral age key was lost. No production adoption claim was made. [Assessment](docs/platform/WARDYN_FIT_ASSESSMENT.md).

## 2026-11-12T14:14:22+05:30 — Wardyn approval and audit evaluation

- **Commit:** [`cc3a4cb`](https://github.com/ChaitanyaPandit1998/sandboxing/commit/cc3a4cb).
- **Successful:** Recorded synthetic pending egress approvals, approval/denial decisions, and audit events.
- **Limits:** Decisions used an admin token; human OIDC attribution and organization authorization were not tested. Wardyn device-login integration remained a separate question from the POC's later authenticated gateway runs.

## 2026-11-12T02:47:30+05:30 — Repository organization and nightly runtime evidence

- **Commit:** [`ffd87b5`](https://github.com/ChaitanyaPandit1998/sandboxing/commit/ffd87b5).
- **Changed:** Organized scripts, docs, profiles, and results; recorded `runsc-next` regressions and documented runtime candidates.
- **Limits:** Candidate/runtime regression success did not constitute promotion or full platform readiness. [Agent validation plan](docs/validation/AGENT_SESSION_VALIDATION_PLAN.md).

## 2026-11-12T01:28:39+05:30 — Expanded real-agent security validation

- **Commit:** [`42035bb`](https://github.com/ChaitanyaPandit1998/sandboxing/commit/42035bb).
- **Changed:** Expanded CLI compatibility, filesystem/process boundaries, egress, and launch-policy validation with evidence and explicit limitations.
- **Limits:** Selected benign/denied probes do not prove escape resistance or comparative security superiority. [Validation plan](docs/validation/AGENT_SESSION_VALIDATION_PLAN.md).

## 2026-11-11T14:07:56+05:30 — Executive brief and security plan

- **Commit:** [`08e4e92`](https://github.com/ChaitanyaPandit1998/sandboxing/commit/08e4e92).
- **Changed:** Added a leadership summary and prioritized threat-driven security validation plan. Planned cases were kept distinct from executed results.

## 2026-11-11T13:37:54+05:30 — Summary and metric visuals

- **Commit:** [`8cc26f2`](https://github.com/ChaitanyaPandit1998/sandboxing/commit/8cc26f2).
- **Changed:** Added the POC summary and charts for measured runtime performance and selected safety outcomes. Subsequent findings supersede earlier interpretations where documented.

## 2026-11-11T01:25:12+05:30 — Compare seccomp profile outcomes

- **Commit:** [`cf99902`](https://github.com/ChaitanyaPandit1998/sandboxing/commit/cf99902).
- **Changed:** Compared Docker's built-in seccomp behavior with a pinned derived probe overlay.
- **Finding / limits:** Some `runc` errno outcomes changed while selected `runsc` outcomes stayed constant. Errno differences alone do not identify every enforcement layer or prove one runtime more secure. [Report](docs/reports/REPORT.md).

## 2026-11-11T00:56:16+05:30 — Safe syscall matrix

- **Commit:** [`53aad44`](https://github.com/ChaitanyaPandit1998/sandboxing/commit/53aad44).
- **Changed:** Added a bounded diagnostic matrix using harmless/invalid syscall requests under matched policies; this was not fuzzing or exploit testing.

## 2026-11-11T00:26:43+05:30 — Negative controls

- **Commit:** [`4b3f4d0`](https://github.com/ChaitanyaPandit1998/sandboxing/commit/4b3f4d0).
- **Successful:** Detected ten deliberately weakened runtime/scenario cases across both runtime paths.
- **Fix:** Mount validation checked both Docker's `HostConfig.Binds` and top-level `Mounts`, covering `--mount` as well as bind flags.

## 2026-11-10T23:43:18+05:30 — Boundary and egress probes

- **Commit:** [`d1e3a5e`](https://github.com/ChaitanyaPandit1998/sandboxing/commit/d1e3a5e).
- **Changed:** Added privilege/filesystem/process boundary checks and an internal-client-network/explicit-proxy egress design.
- **Limits:** Basic allow/deny passes were later qualified by the recorded TLS hostname bypass. [Current report](docs/reports/REPORT.md).

## 2026-11-10T21:42:33+05:30 — Initial local runtime POC

- **Commit:** [`3f70d4a`](https://github.com/ChaitanyaPandit1998/sandboxing/commit/3f70d4a).
- **Changed:** Established paired `runc`/`runsc` workload experiments inside a dedicated ARM64 Lima Linux VM, with matched images/limits and raw result capture.
- **Finding / limits:** CPU, temporary I/O, and loopback HTTP timings covered synthetic workloads on one VM. Later warmed/alternating and TCP-setting controls refined interpretation; they did not establish application performance or security guarantees.

## Recording future work

Add a new entry for each meaningful implementation, documentation, or validation batch, including failed attempts that affect the result. Use the actual IST record time, or explicitly mark date-only historical evidence. Record commit time separately from execution time and do not claim a push without observing it.

```text
## YYYY-MM-DDTHH:MM:SS+05:30 — Short description
- Changed: concrete files/behavior and reason.
- Validation: checks actually run, result, and evidence links.
- Failed / remaining: relevant failures, scope limits, unresolved work.
- State: uncommitted, or commit ID and observed push status.
- Next: immediate follow-up.
```

Never include login codes, credentials, private keys, raw auth files, or private user prompts. Update the [requirements matrix](docs/REQUIREMENTS_STATUS.md) when coverage changes; this log is history, not the source of current requirement status.

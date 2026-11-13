# Development log

Changes are recorded newest first. All timestamps use **Asia/Kolkata (IST, UTC+05:30)**.

Historical commit timestamps below are exact Git **author timestamps**, not test execution or push times. Entries marked **date only** have no independently recorded wall-clock execution time; no time has been invented. Entries without an explicit SHA may refer to the consolidation commit that contains them; use Git history for its exact ID. Relative test timings measure durations, not time of day.







## 2026-11-13T15:30:01+05:30 — Commit monitoring UI, durable alerts and validation evidence

- **Scope:** Consolidated the policy/telemetry/site-policy UI, resident security journal, local alert review workflow, foreground login adjustment, recovery/concurrency/coding validators, sanitized evidence and documentation for commit/push at the user's request. Earlier uncommitted-state entries reflect their batch-time status.
- **Checks:** Git whitespace validation, JavaScript/shell syntax, AST parsing of 13 Python files and JSON validation of 17 evidence files passed. Targeted credential-pattern scan found no candidates. Existing evidence records six journal tests, four sanitization/policy tests, 16 API tests (one separate live lifecycle test skipped), 11 isolated service checks and the actual denied-flow/browser/restart workflow. Historical failed Python-task evidence is intentionally retained alongside the successful Node follow-up. No additional model calls or runtime changes were made for this commit-only step.
- **Next:** Define detection thresholds/review criteria and expand signal coverage, then reviewed delivery and organization authorization. Git history and the remote record the resulting commit/push status.


## 2026-11-13T15:21:49+05:30 — Durable security history and local alert review

- **Changed:** Added private SQLite journal/alert/audit tables with additive idempotent schema setup; resident collection outside the Mac console; flow-stage deduplication, lifecycle cursor, drift episodes, local acknowledgement/resolution, reopen on new evidence, validated history pagination and UI filters/action trail. Journal retains up to 10,000 events/30 days; resolved alerts retain 30 days from resolution, unresolved alerts remain. Updated installer/dependency copies and deployed the collector/API/UI. No external messages or notifications.
- **Validation:** Six journal tests, four sanitization/policy tests and 16 API tests passed; one separate live lifecycle test skipped. Updated resident service passed 11 isolated checks. A disposable pilot session generated two actual denied CONNECT flows; resident collection independently opened/reopened the same alert, count stayed two after resampling/restart, and API/browser acknowledge/resolve succeeded. Browser verified two filtered history entries and six actor-labeled actions with no console errors. State/history survived collector and Mac console restarts. [Evidence](results/security-history-20261113/).
- **Corrections:** Fixed a placeholder-count error before tests; caught a resolved-retention edge case and added explicit resolution time plus a regression test so old unresolved items do not disappear immediately upon review. One browser selector missed the summary element; selected its visible text and completed the audit review. No user data or policy protections were relaxed.
- **Limits / cleanup:** Journal is local and not tamper-resistant; actor is a fixed trusted-operator label. Polling can miss bursts/removed gateway logs/downtime gaps; no blocked-hostname history, prompt-injection/malware detection, historical utilization or external delivery. No credentials, codes, raw URLs, headers, bodies or model outputs stored. Disposable session stopped with workspace retained; its resolved validation alert/history intentionally retained. Existing coding session had already expired under its original deadline before this validation.
- **State / next:** Loopback backend and resident service running. Preview saved to /private/tmp/sandbox-console-alert-history.png. Docs updated; changes remain uncommitted/unpushed. Next define detection thresholds/review criteria and expand signal coverage, followed by reviewed delivery and organization authorization.


## 2026-11-13T13:52:05+05:30 — Policy, telemetry, review signals and blocked-site UI

- **Changed:** Added four real console sections, compact/desktop navigation, session-state filters, current agent resource samples, nine selected policy-configuration checks, evidence-based timing bars, review-signal filtering and local exact-hostname policy lookup. New read-only authenticated `/api/monitor` forwards a bounded sanitized worker snapshot; policy administration is not exposed. Updated installer to include the monitoring module and deployed it to the pilot worker. Restarted only the owned loopback backend.
- **Successful:** Live snapshot verified all nine checks and CPU/memory/PIDs; sampled gateway denies appeared as review signals. Fourteen local API tests passed, one separate live lifecycle test skipped; three sanitization/policy tests passed, including seven deliberate weakening cases and unavailable-resource handling. JS/Python/shell syntax and Git whitespace checks passed. Native browser reviewed desktop/narrow layouts, active/history filters, approved/unapproved/lookalike domain lookups, signal filtering, charts, and zero console errors. [Evidence](results/console-monitoring-20261113/).
- **Corrections / limits:** Narrow layout initially hid sidebar links and long stopped history crowded the page; added compact section navigation and active/history filters. Sampling is up to 200 gateway log lines/15m, decisions not unique requests. No blocked-hostname history, raw logs, credentials, headers or bodies returned. Review signals do not establish malicious activity; prompt-injection/malware detection, durable incidents, central alerts, policy editing, historical telemetry and full security acceptance remain pending. No VM restart, image rebuild, session stop or auth change in this batch.
- **State / next:** User's coding session remains on its existing expiry; browser preview saved to /private/tmp/sandbox-console-monitoring.png and viewport override reset. Docs updated; changes remain uncommitted/unpushed. Next define detection rules/retention and alert handling, then safe policy administration and organization authorization.


## 2026-11-13T13:20:32+05:30 — Real coding/tool task validated with installed runtime

- **Successful:** Private login eventually verified in the fresh session. Node coding task wrote implementation/tests, ran a successful command and passed independent correctness assertions plus five generated tests. First message 4.233s, first tool 5.121s, completed turn 21.206s, CLI exit 22.099s. [Outcome](results/coding-task-20261113/node-task.json), [summary/source hashes](results/coding-task-20261113/summary.json).
- **Failed / corrected:** Initial Python task created files but failed execution/independent validation because this agent image has no python3 (Node 22.23.4 is available). Preserved [failed attempt](results/coding-task-20261113/attempt-1.json); changed the fixed task/oracle to installed Node built-ins and added runtime preflight, without rebuilding image or weakening policy. The successful Node run still had one intermediate nonzero command; its cause was not captured by the sanitized counter-only harness. No claim of zero tool failures.
- **Validation / limits:** Verified five tests exit 0 and both generated files in the dedicated workspace subdirectory. Python syntax checks on four changed/new scripts and Git whitespace checks passed. One after-login automated CLI task; no token-level TTFT, interactive attach, p95, uptime or general Python compatibility claim. Login-wait cause remains unconfirmed. No credentials, codes or raw model output saved.
- **State / next:** Left coding session ready until its existing deadline (no extension) for further checks; workspace retained. Updated runbook, executive summary and requirement evidence. Changes uncommitted/unpushed. Next repeated timing and safe intermediate-error classification, image capabilities, then interactive attach and uptime testing.


## 2026-11-13T13:13:34+05:30 — Investigate coding-session device authorization wait

- **Observed:** Fresh coding session ready; Codex login process still running; login status not authenticated. Gateway running, no OOM, nine sampled allow decisions and zero deny decisions. Dedicated login log found but no fixed-category timeout/token-exchange/certificate errors recorded. No raw logs, auth files, bodies or codes saved. [Evidence](results/coding-task-20261113/login-diagnostic.json).
- **Correction / limits:** A naive substring count initially matched digits 502 in policy JSON; excluding JSON flow IDs found no explicit HTTP 502/error evidence. Do not interpret arbitrary digit matches as response status. A shell-quoting error in the first diagnostic was corrected by staging a script. These diagnostics do not identify the cause of the authorization wait. No gateway restart or policy relaxation was applied.
- **Next:** Asked user to distinguish account sign-in from completed device-code approval, following [official authentication documentation](https://learn.chatgpt.com/docs/auth?surface=cli). Coding task remains gated on verified login. Changes remain uncommitted/unpushed.


## 2026-11-13T13:09:10+05:30 — Prepare real coding/tool task and timing capture

- **Changed:** Added and staged `scripts/test_managed_coding_task.py`: fixed Python implementation/unittest task, bounded streaming JSON-event timing, independent in-container correctness/test validation, sanitized outcomes only. Created a fresh one-hour managed session after prior concurrency-test cleanup.
- **Validation / state:** Python syntax passed; VM staging succeeded. Fresh session is ready, but private login status is false. No model/tool task has run and no performance claim is made. [Preparation evidence](results/coding-task-20261113/preparation.json).
- **Limits:** First response is an observed message event, not token-level TTFT. This will be one task after manual login, excluding provisioning; no p95 or uptime evidence. No credentials/codes/raw model output recorded.
- **Next:** User completes private device login, then run coding task and report first-event, response, tool and completion timings. Changes remain uncommitted/unpushed.


## 2026-11-13T13:01:43+05:30 — Five authenticated concurrent model probes passed

- **Successful:** Verified independent private sign-in in all five ready sessions, then ran the fixed reply-only probes concurrently. Five of five passed with expected reply, exit 0, completed turns and zero recorded error events. Completed-response times 36.284–38.690s, median 37.648s; batch 38.693s. [Evidence](results/five-session-pilot-20261113/authenticated.json), [summary](results/five-session-pilot-20261113/summary.json).
- **Cleanup / docs:** Stopped the five completed test sessions, retaining managed workspace data and removing temporary homes/keys/networks. Updated worker runbook, requirement matrix and executive summary. No credentials, login codes or raw model output saved.
- **Limits / failures:** Earlier HTTP 504 origin remains unresolved; foreground-login retries succeeded but causality is unproven. One account, five reply-only tasks; no tools, browser attach, reliable p95 or uptime claim. Response times exclude provisioning and human login; startup and model-completion targets must be assessed separately.
- **Next / status:** Repeated readiness decomposition, authenticated interactive tool task, sleep/recovery and uptime testing. Changes remain uncommitted/unpushed.


## 2026-11-13T12:56:58+05:30 — Foreground private login retry

- **Observed:** Sessions 1–3 verified logged in; 4–5 not logged in. User reported browser approval while session 4 Terminal waited. In-container process-name inspection showed only sleep and the diagnostic node process, with no active Codex login poller. Gateway running, no OOM or sampled error/deny indicators; deadline still in future. No credentials or raw request data were inspected.
- **Changed / validation:** Managed interactive login now uses the supported global `--no-daemon` flag, matching attach's existing foreground behavior. Deployed to VM; Python syntax passed; status recheck preserved the three logins. The original cause and successful retry remain unverified; no claim of resolution.
- **Next:** User restarts the private helper for sessions 4–5; run concurrent model probes only after all five report logged in. Changes remain uncommitted/unpushed.


## 2026-11-13T12:28:02+05:30 — Device-login timeout diagnostic

- **Successful:** Session 1 remains privately logged in; all five sessions remain ready and resident cleanup is healthy. Verified TLS requests to the public device page returned HTTP 302 in 0.069/0.088s from sessions 1/2. Both gateways were running with no OOM and no observed policy denials in the sampled logs.
- **Failure / limits:** Session 2 device authorization returned HTTP 504 in the user's terminal. Current public-page reachability does not identify the historical timeout's origin or validate the token endpoint. No codes, tokens, bodies or raw gateway logs were saved. [Sanitized evidence](results/five-session-pilot-20261113/login-timeout-diagnostic.json).
- **Next:** Re-run the private helper, which skips verified session 1, obtains fresh login challenges for the remaining sessions and checks persistence. Five-session authenticated model probing remains pending. Changes remain uncommitted/unpushed.


## 2026-11-13T12:25:31+05:30 — Actual VM restart and five-session preparation

- **Changed:** Added explicit isolated VM recovery phases and a five-session private-login/probe helper. Restarted the idle POC VM with no active pilot containers; cleanup services resumed automatically. Prepared five sessions under the existing one-hour policy. Updated current worker/requirement documentation.
- **Successful:** [Nine actual stop/start checks](results/vm-recovery-20261113/restart.json) passed, covering automatic service startup, overdue/lost-session cleanup, resource removal and retained workspace marker. Recovery test unit/state/volume were removed; production service remained healthy. [Five login-ready timings](results/five-session-pilot-20261113/login-ready.json) ranged 0.788–4.259s including serialization, with all five simultaneously ready.
- **Failures / pending:** User reported login, but all five new sessions returned not-logged-in with no auth file present (presence checked without reading credentials). Authenticated probe correctly refused to run. Added per-session verification and requested private sign-in again. One CLI-help inspection used an incorrect container namespace; corrected by resolving the name from Worker. No model requests or credentials were captured.
- **Limits:** One VM restart, no actual Mac sleep, clock-jump or uptime soak; five timings are not reliable p95 evidence and exclude human login. This is one account across five sessions, not five users. Authenticated test awaits private login; sessions expire normally after one hour. Changes remain uncommitted/unpushed.
- **Next:** Verify all five private logins, run the concurrent fixed model probes, then clean up test sessions and report authenticated response timings separately from provisioning.


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

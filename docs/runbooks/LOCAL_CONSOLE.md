# Local session console

**Status (2026-11-13):** real single-user console and loopback API implemented. Create, list, inspect, lifecycle events, stop, and idempotent requests operate the managed Lima worker. Login and interactive Codex use private Mac Terminal commands copied from the UI; browser terminal relay is not implemented.

## Start

From the repository root on the Mac, with `gvisor-poc` running and the [managed worker](MANAGED_WORKER.md) installed at `~/gvisor-managed-pilot/` inside that VM:

```bash
python3 scripts/serve_session_console.py --port 4180
```

Open **http://127.0.0.1:4180/**. Use that exact address; Host checks intentionally reject alternate hostnames. Keep the server terminal open. Stop the server with Ctrl+C. New sessions receive a one-hour deadline. The backend checks cleanup every 30 seconds, including when the browser page is closed. The resident VM service continues cleanup when this backend closes. VM/Mac suspension or downtime pauses cleanup; overdue sessions are reconciled when the VM service resumes. Existing legacy sessions have no deadline and require manual stop. Use Stop for immediate teardown.

## Workflow

1. Create a session using the fixed approved pilot policy. The backend applies the worker's five-session quota and serialized provisioning.
2. Inspect shows real lifecycle/policy metadata and loads recorded events. Ready means **login-ready**, not authenticated model readiness.
3. Login shows a managed device-login command for Mac Terminal. Complete sign-in privately.
4. Open Codex shows the managed attach command for that same session. Paste it into Mac Terminal; the browser never handles terminal contents, one-time codes, or provider credentials.
5. Stop removes the session, gateway, temporary login home, and networks. The pilot's workspace volume is retained and shared across its sessions.

The console polls worker state and disables create when the worker is unavailable. Overview runtime/resource cards describe fixed policy. The Telemetry section samples current agent CPU, memory and PIDs, with timestamps; session-state filters show active or historical sessions. Review signals cover selected policy drift, sampled egress denials and operational failures. Automated attack detection, central alerts and historical utilization remain pending.

## Local security boundary

The server binds only to 127.0.0.1. API requests use a process-local HttpOnly/SameSite cookie; mutations also require a CSRF token. Host, Origin, and Fetch Metadata checks reject unrelated website origins. Requests accept only the fixed policy, bounded JSON, validated session IDs, and narrowly defined actions. The browser cannot submit Docker flags, worker commands, mounts, images, or shell text. Static file serving is limited to the console assets and Markdown/SVG documentation.

Bootstrap is deliberately available to the local browser: this is not organization authentication. Other processes/users on the same Mac may reach the loopback API, so the machine must have a trusted operator environment. Add real identity/authorization and a reviewed transport before any remote or mutually untrusted multi-user deployment. There is no remote bind option.

No request headers/cookies/bodies are logged. The API forwards only known worker operations to Lima, using argument arrays rather than client-controlled shell commands. It returns sanitized worker metadata/error codes. Browser terminal handoff is specific to this trusted local pilot; it does not implement the future attach-ticket/relay contract.

## Validation

- **12 tests passed:** 11 local HTTP/static boundary tests plus one live worker lifecycle containing eight assertions for create, idempotency, list, inspect, events, terminal handoff, stop, and repeated stop. The live test used a separate synthetic state/volume and removed it afterward.
- Host rebinding, cross-origin/site requests, missing local session/CSRF, policy overrides, invalid IDs, traversal, and unsafe methods were rejected in the tested cases.
- A native terminal launch of the managed attach command displayed Codex 0.167.1 and its sign-in menu, then exited cleanly on Ctrl+C. No login/model request was made during that probe. The earlier automated pseudo-terminal detector did not recognize a screen; the native terminal check confirmed launch.
- A separate console API create/stop used the actual pilot namespace. Diagnostic sessions were stopped; the intended persistent workspace remains.
- JavaScript syntax, DOM IDs, assets, API responses, and documentation links were checked. Browser review subsequently verified live rows, Inspect/close, recorded events, the expiry column, cleanup status, and responsive action visibility. Create/stop remain verified through the HTTP integration tests; they were not graphically exercised against the user’s active session.

Evidence: [API checks](../../results/session-console-20261113/api-checks.json), [terminal launch](../../results/session-console-20261113/terminal-attach.json), and [asset checks](../../results/session-console-20261113/assets.json). Test command:

```bash
POC_LIVE_CONSOLE=1 python3 -m unittest discover -s tests -p test_session_console.py -v
```

The live test provisions synthetic Docker resources. Next validate authenticated interactive attach and VM restart recovery, and complete the decision on organization control-plane integration. Five-session authenticated readiness and service uptime remain unmeasured.

## One-hour expiry follow-up

The user selected one hour for new sessions. Inspect returns `expires` and `stop_reason`; the table displays each deadline and labels expired stops. Idempotent create does not extend a deadline. Expiry removes temporary containers, networks, login homes and gateway keys, while retaining the workspace. A migrated session with a null deadline remains unchanged.

The worker passed [22 checks](../../results/session-expiry-20261113/worker.json), including expiry cleanup, workspace retention and legacy-session preservation. The updated server passed [13 tests](../../results/session-expiry-20261113/api-background.json), including a real synthetic session expired by the background sweeper without any browser request. Tests injected a past timestamp instead of waiting one hour.

The resident VM service now enforces polling independently of the Mac backend; the console sweeper remains a fallback. The UI reports resident active/stale/error status. VM/Mac suspension, downtime, clock changes or cleanup failure can delay expiry; this is not a hard deadline guarantee. See [resident service operations](MANAGED_WORKER.md#resident-cleanup-service).


## Security and observability views (2026-11-13)

The new navigation opens four implemented sections:

- **Policy checks:** Nine selected checks from owned container/network metadata: runtime, non-root user, read-only root, no-new-privileges, nonprivileged/dropped capabilities, resource limits, internal network, workspace/public-CA mount boundary, and gateway hostname configuration. No active session or unavailable metadata displays unmeasured, not passed. These are configuration checks, not a complete security assessment.
- **Telemetry:** Read-only `/api/monitor` samples active agent containers using Docker CPU/memory/PIDs. Monitoring refreshes every 30 seconds; session state refresh remains every eight seconds. Recorded coding timings are loaded separately from checked-in sanitized evidence and labeled as one after-login validation task. No gateway utilization, historical resource chart or uptime SLO is claimed.
- **Suspicious activity / review signals:** Filterable policy drift, bounded gateway deny signals and recent lifecycle failures. They are review indicators, not attribution of an attack; validation traffic can trigger denials. There is no prompt-injection/malware detector or central alert delivery. Live sampled signals are derived on request; the separate resident journal and local alert workflow below retain selected events.
- **Allowed / blocked sites:** Shows the fixed three exact HTTPS hostnames and explains default deny for everything else. The hostname checker performs only a local policy lookup, without DNS/HTTP requests. Policy editing is not exposed. Hostnames of blocked attempts are deliberately not captured; the UI cannot present a per-domain blocked-traffic history.

Gateway sampling reads at most 200 log lines per active gateway from the previous 15 minutes and accepts only known JSON decision/reason fields. Counts represent logged decisions, not unique network requests. Unknown/malformed log entries, URLs, headers, bodies and arbitrary extra fields are discarded. Missing samples and failed monitoring requests are shown as unavailable/stale. This remains a trusted local operator API, not an organizational security dashboard.

Validation: **14 local API tests passed** (one separate live lifecycle test skipped in this batch), **three sanitization/policy tests passed** including seven weakened-configuration cases and unavailable-resource handling, and the real API/worker snapshot passed. Live browser checks verified nine passing checks, current resource data, timing bars, deny-review signals, active/history filters, approved/blocked/lookalike hostname lookups, narrow/desktop navigation and no console errors. No user session was stopped or logged out. [Evidence](../../results/console-monitoring-20261113/).

Next: extend the implemented local journal/alert workflow with explicitly defined suspicious-activity rules, safe policy administration with change review, historical resource collection, and organization identity/authorization. These views do not close the requirements acceptance gaps on their own.


## Durable history and local alerts (2026-11-13)

**Implemented:** Event history, local alert state filters, Acknowledge/Resolve controls, event-type filters, bounded pagination and alert action history. Collection runs in the supervised VM service even with the browser and Mac backend closed. `/api/alerts` and `/api/security-events` read the private worker SQLite journal. Alert mutations use `/api/alerts/{id}/acknowledge` or `/resolve`, with the same loopback session, Origin/CSRF, fixed-body and ID checks as other mutations. Client-supplied actors, notes or arbitrary commands are not accepted.

- Gateway denials are deduplicated by a hash of session, flow ID and policy stage. Re-reading overlapping logs does not increase counts or reopen a resolved alert. Only known decision/reason fields are accepted; raw flow IDs, URLs, bodies, headers and credentials are not stored.
- Lifecycle records use a sequence cursor. Selected policy drift creates one event per failing episode; a verified healthy observation followed by drift starts a new episode. Missing observations do not establish recovery.
- Alerts group by session and signal type. Acknowledge records operator review; Resolve changes review status without remediating policy. A distinct new event reopens a resolved alert. Already-acknowledged alerts remain acknowledged as new evidence increments their count.
- Alert actions record the fixed actor `local-operator`; collector actions record `collector`. This is the trusted local pilot, not an SSO identity or tamper-resistant organizational audit trail. No email, Slack or other external notification is sent.
- The journal retains at most **10,000 events for up to 30 days**, whichever removes records first. Resolved alerts and their action trail are retained for **30 days after resolution**; unresolved alerts remain until reviewed. The original worker lifecycle database and workspace have separate retention behavior. This is not a full database byte quota.
- History requests return at most 100 records using a validated cursor/type filter. The browser displays at most 500 loaded history records before asking the operator to reload newest or narrow the filter. The alert list shows the newest 100 alerts; counters cover all retained alerts.

Collection is polling-based. It samples at most 200 gateway log lines from the last 15 minutes per active session. Fast bursts, stopped/removed gateways before collection, and downtime longer than that window can miss traffic events. Gateway journal timestamps are first-observed collection times, not packet times; lifecycle timestamps come from the worker. The collector shows its last collection time and incomplete sample count. Unavailable/stale collection is not proof of an incident-free period. Historical traffic before this collector was installed is not reconstructed.

**Validation:** Six journal tests and four sanitization/policy tests passed; 16 local API tests passed with one separate live lifecycle test skipped. The journal-enabled resident service passed 11 isolated service checks. A disposable real pilot session generated two rejected CONNECT flows (403, no allowed outbound website request). Resident collection opened an alert, API acknowledgement/resolution succeeded, a new flow reopened it with count two, and service resampling did not duplicate it. Browser acknowledgement/resolution, state/type filters, two retained denial events and six action records were verified with no console errors. Alert state/history survived collector and Mac console restarts. The test session was stopped and workspace retained; its resolved validation alert remains as evidence. [Results](../../results/security-history-20261113/).

Next: define detection thresholds and review criteria, extend signal coverage, add reviewed external delivery if required, and implement organization authorization. These additions do not detect prompt injection or malware and do not close the full security/uptime acceptance gates.

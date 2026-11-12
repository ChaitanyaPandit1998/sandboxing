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

The console polls worker state and disables create when the worker is unavailable. Runtime/resource cards describe the fixed policy, not measured resource consumption. It has no suspicious-activity alerts or usage monitoring yet. Historical stopped sessions remain visible.

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

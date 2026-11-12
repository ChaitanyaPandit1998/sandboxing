# Managed local Codex worker

**Status (2026-11-13):** first local worker implementation. This is a trusted single-operator CLI inside the Linux VM, not the HTTP control plane, browser terminal, SSO, or a production service. It supplies an integration boundary for a future control plane while Wardyn compatibility remains under evaluation.

## Implemented behavior

- Create, list, inspect, login, attach, stop, reconcile, and lifecycle-event commands.
- Fixed digest/image IDs, stable runsc runtime, non-root identity, dropped capabilities, no-new-privileges, read-only root, resource limits, internal client network, TLS gateway, public CA trust, and explicit HTTPS Codex provider.
- One Docker workspace volume per local pilot/state namespace. All sessions for that local pilot share it. Stop retains workspace data; session homes and gateway CA keys are temporary. No credentials are automatically copied to the workspace or replacement sessions.
- Durable private SQLite metadata and redacted lifecycle events in `~/.local/state/gvisor-poc-worker` (directory mode 0700; database 0600).
- Create idempotency via a hashed request key, idempotent stop, and a five-active-session quota. Creation is serialized by a local process lock, so simultaneous requests include queue time.
- Ownership labels checked before deleting containers/networks. Reconcile cleans interrupted provisioning and lost-container sessions. It runs before create/login/attach and through an explicit command; new sessions have a one-hour deadline. The installed systemd user service reconciles every 30 seconds independently of the Mac console; the console provides a fallback sweep.

## Use inside the VM

Keep `tls_gateway.py` and the script in the repository layout, with the tested agent/gateway images and runtime already available:

```bash
python3 scripts/manage_codex_session.py create --key my-first-session
python3 scripts/manage_codex_session.py list
python3 scripts/manage_codex_session.py inspect SESSION_ID
python3 scripts/manage_codex_session.py login SESSION_ID
python3 scripts/manage_codex_session.py attach SESSION_ID
python3 scripts/manage_codex_session.py events SESSION_ID
python3 scripts/manage_codex_session.py stop SESSION_ID
python3 scripts/manage_codex_session.py reconcile
```

Use an actual returned ID in place of `SESSION_ID`. A key identifies one create request permanently; use a new key for a new session after stop. Login and attach require an interactive terminal and relay directly to the approved container's Codex CLI. Device login stays private in that terminal. A native terminal launch displayed Codex and its sign-in menu and exited cleanly; an authenticated interactive task through attach remains unverified. Managed device login and noninteractive authenticated tasks have been exercised.

The [local console](LOCAL_CONSOLE.md) now provides real create/list/inspect/stop/events over this worker. Its Login and Open Codex actions hand off fixed commands to Mac Terminal rather than exposing a browser terminal.

The staged pilot copy is `~/gvisor-managed-pilot/scripts/manage_codex_session.py` inside the VM. From Mac Terminal:

```bash
limactl shell gvisor-poc -- bash -lc 'python3 "$HOME/gvisor-managed-pilot/scripts/manage_codex_session.py" list'
```

`ready` means the gateway listener, writable workspace, and CLI startup passed; its separate `readiness` field says that login is required. It is not an authentication or provider-health check. Metadata inspection does not automatically reconcile stale state; invoke `reconcile` to refresh resource-loss state.

## Live validation

All **17 synthetic integration checks passed**: idempotent create/stop, approved runtime settings, managed volume and temporary home/public-CA separation, verified provider TLS (unauthenticated 401), hostname mismatch denial, workspace persistence, five simultaneous active sessions, sixth-session rejection, lost-gateway cleanup, interrupted-provisioning reservation/network cleanup, invalid ID rejection, foreign-resource preservation, arbitrary image override rejection, and lifecycle event recording.

Five concurrent CLI create requests reached login-ready in **1.117, 2.245, 5.707, 4.535, and 3.393 seconds**. These are five observations from one cached-image run, including serialization/queue time. They are not an authenticated five-user test, a full service request-to-ready measurement, or a reliable p95 estimate.

Evidence: [synthetic checks](../../results/managed-worker-20261113/checks.json) and [source/environment fingerprints](../../results/managed-worker-20261113/environment.json). The test helper removes only its synthetic workspace volume; normal `stop` preserves the pilot volume. Test-owned resources were verified removed before creating the real pilot session.

An authenticated follow-up through the provisioned pilot session also passed: private ChatGPT device login through the managed `login` command, a fixed workspace-write task (exit 0, 9.871s, zero error events), managed stop, replacement create, and persistence of the model-written marker. The replacement had no login state. Both sessions were stopped; their credential homes, gateway keys, and temporary networks were removed while the pilot workspace volume was retained. See [authenticated evidence](../../results/managed-worker-20261113/authenticated.json). This is one model task, not a latency distribution or five-authenticated-session readiness measurement.

## Remaining boundaries

The CLI trusts the local OS operator, who already has Docker access. It has no remote authentication, cross-user authorization, browser attach tickets, automatic grant revocation, tamper-resistant audit, organization API/authorization or service uptime monitoring. Resident VM reconciliation is implemented; it pauses during VM/Mac suspension or downtime and is not a hard deadline guarantee. Persistent workspace deletion/retention, backup, and byte quotas remain open. Loss of gateway CA/tmpfs after container/VM restart may require session replacement; current reconciliation checks container running state rather than complete TLS health. Do not expose this CLI as an unauthenticated remote command endpoint.

Next connect the worker to the selected control plane, validate authorization and cleanup through that service, and measure authenticated concurrent readiness and attach latency. Keep the top-level requirements partial until those gates pass.

## Session expiry

New creates set `expires = created + 3600`; idempotent retries preserve that deadline. Existing database rows migrate with null deadlines and are not retroactively expired. Reconciliation records `expiry_reached`, stops overdue sessions with `stop_reason=expired`, and retains their workspace volume. It runs before create/login/attach, explicitly on command, and in the console's background loop.

The [expanded worker suite](../../results/session-expiry-20261113/worker.json) passed 22 checks, including expired-resource cleanup, persistent workspace, unchanged retry deadline, and legacy no-deadline behavior. The [API background check](../../results/session-expiry-20261113/api-background.json) also passed. Resident reconciliation now removes the Mac-backend dependency; VM downtime and suspension still delay polling.


## Resident cleanup service

The pilot now runs `gvisor-poc-reconciler.service` in the existing VM user's systemd manager. It reconciles every 30 seconds, restarts on process failure, and writes atomic private health metadata. Existing user lingering was already enabled, allowing it to run after logout. It has no network listener or model calls. Legacy sessions keep their null deadlines; workspaces survive expiry.

To install/update, copy this repository's service sources into the VM and run `bash scripts/install_worker_reconciler.sh` there. The installer requires existing user lingering and does not change global AppArmor, user-namespace settings, Docker daemon policy, or session isolation. From Mac Terminal:

```bash
limactl shell gvisor-poc -- systemctl --user status gvisor-poc-reconciler.service
limactl shell gvisor-poc -- python3 /home/chaitanya.guest/gvisor-managed-pilot/scripts/manage_codex_session.py health
```

`systemctl --user restart gvisor-poc-reconciler.service` restarts the supervisor unit inside the VM. Stopping/disabling it pauses resident cleanup; the console sweep is only a fallback while its backend runs.

[Eleven isolated checks](../../results/resident-cleanup-20261113/service.json) passed: service startup/private health, injected overdue expiry without console requests, expiry reason, temporary-container removal, volume/data retention, killed-process restart, and a test-only Docker-socket failure/recovery. [Fourteen API tests](../../results/resident-cleanup-20261113/api-tests.txt) passed, and the real console reports [healthy resident status](../../results/resident-cleanup-20261113/live-health.json). No model calls, VM reboot, one-hour soak, or clock-jump tests were performed.

The first unit failed at systemd's CAPABILITIES step with mount/device namespace sandboxing in this unprivileged user manager. The tested unit uses `NoNewPrivileges`, an AF_UNIX address-family restriction and a private umask; it does not sandbox the trusted worker's filesystem. The worker already has powerful Docker socket access. Container protections remain unchanged. This is a single trusted operator boundary, not an organizational control plane or an uptime SLO.

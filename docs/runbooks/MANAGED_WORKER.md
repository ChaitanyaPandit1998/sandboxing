# Managed local Codex worker

**Status (2026-11-13):** first local worker implementation. This is a trusted single-operator CLI inside the Linux VM, not the HTTP control plane, browser terminal, SSO, or a production service. It supplies an integration boundary for a future control plane while Wardyn compatibility remains under evaluation.

## Implemented behavior

- Create, list, inspect, login, attach, stop, reconcile, and lifecycle-event commands.
- Fixed digest/image IDs, stable runsc runtime, non-root identity, dropped capabilities, no-new-privileges, read-only root, resource limits, internal client network, TLS gateway, public CA trust, and explicit HTTPS Codex provider.
- One Docker workspace volume per local pilot/state namespace. All sessions for that local pilot share it. Stop retains workspace data; session homes and gateway CA keys are temporary. No credentials are automatically copied to the workspace or replacement sessions.
- Durable private SQLite metadata and redacted lifecycle events in `~/.local/state/gvisor-poc-worker` (directory mode 0700; database 0600).
- Create idempotency via a hashed request key, idempotent stop, and a five-active-session quota. Creation is serialized by a local process lock, so simultaneous requests include queue time.
- Ownership labels checked before deleting containers/networks. Reconcile cleans interrupted provisioning and lost-container sessions. It runs before create/login/attach and through an explicit command; there is no background reconciler or expiry scheduler yet.

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

Use an actual returned ID in place of `SESSION_ID`. A key identifies one create request permanently; use a new key for a new session after stop. Login and attach require an interactive terminal and relay directly to the approved container's Codex CLI. Device login stays private in that terminal. Interactive model attach is implemented but has not yet been manually exercised through this manager; managed device login has been exercised.

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

The CLI trusts the local OS operator, who already has Docker access. It has no remote authentication, cross-user authorization, browser attach tickets, automatic grant revocation, tamper-resistant audit, API idempotency semantics, background expiry, or service uptime monitoring. Persistent workspace deletion/retention, backup, and byte quotas remain open. Loss of gateway CA/tmpfs after container/VM restart may require session replacement; current reconciliation checks container running state rather than complete TLS health. Do not expose this CLI as an unauthenticated remote command endpoint.

Next connect the worker to the selected control plane, validate authorization and cleanup through that service, and measure authenticated concurrent readiness and attach latency. Keep the top-level requirements partial until those gates pass.

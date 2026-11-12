# Codex session control-plane MVP contract

**Status:** Draft updated 2026-11-12 with agreed pilot decisions. This describes the first real session-management slice; it does not claim these APIs or controls are implemented.

## Product outcome

An organization user can request an approved Codex workspace, wait for it to become usable, attach to it, inspect its state, stop it, and understand what happened. The browser never receives Docker credentials, worker credentials, or arbitrary command execution.

The first release targets Codex CLI and a single-user pilot, with a path to organization SSO later. Target capacity is five simultaneous sessions and request-to-ready p95 is under 25 seconds. Claude Code, arbitrary images, end-user policy authoring, Kubernetes scheduling, snapshot/resume, and broad MCP support remain out of scope unless the pilot requirements change.

The [whiteboard requirement matrix](REQUIREMENTS_STATUS.md) records a longer-term capacity target of 20 concurrent sessions and a stricter p95 startup target below 20 seconds. These differ from the agreed first-pilot targets above; resolve the latency threshold and define the scale-up phase before treating either as a release gate.

## MVP capabilities and current state

| Capability | Required behavior | Current state |
| --- | --- | --- |
| Create | Request a session under a server-approved policy; reject invalid or over-quota requests | Not implemented; current script is operator-run |
| Attach | Give the owner a session-scoped terminal/attach channel without exposing worker or Docker access | Not implemented; operator attaches with `docker exec` |
| Inspect | Show owner, lifecycle state, selected policy/runtime, timestamps, and safe failure reason | Partially evidenced by runner outputs; no service/API |
| Stop / expire | Stop idempotently, revoke grants, clean session home/container/network, apply workspace retention | Script can stop known demo containers; no per-session service or expiry controller |
| Workspace | Give each user a private managed workspace that persists across session stops; apply a declared retention/deletion policy | Current smoke uses memory-backed `/workspace`; no managed persistent workspace |
| Identity / authorization | Authenticate through organization identity and authorize owner/operator/admin actions | Not implemented |
| Runtime policy | Select only a server-approved image, runtime, resources, mounts, and privilege profile | Test scripts use fixed flags; no versioned policy service |
| Egress | Deny direct routes and enforce allowed destinations, including inside TLS tunnels | Direct egress probes pass; strict hostname enforcement is **not achieved** by current proxy |
| Credentials | Keep secrets out of images/workspaces/logs and scope access to a session | Current test uses normal Codex device login in a temporary home; replacement credential design is pending |
| Audit | Record actor, action, target, outcome, timestamp, and correlation ID without prompt/secret leakage | Raw experiment evidence exists; no product audit store |
| Quotas / workers | Bound per-user and organization capacity; detect unhealthy workers and clean orphaned sessions | Not implemented |

## Roles and authorization baseline

For the first single-user pilot, bind the service to loopback and authorize the one local operator; do not expose this mode to a network or multiple users. Add organization SSO (OIDC or approved equivalent) before remote or multi-user access. The backend can then map authenticated identities to one organization and these roles:

- **Member:** create, list, inspect, attach to, and stop sessions they own.
- **Operator:** inspect and stop sessions in the pilot organization; view operational failure details.
- **Administrator:** manage the approved policy and organization quotas.

Every read and mutation checks the principal against the session owner or required organization role. An opaque session ID is not an authorization mechanism. Cross-user access is denied by default. Record denied access attempts in the audit log.

## Versioned policy boundary

The client submits a policy identifier, not Docker flags. The control plane resolves that ID to a versioned server-owned policy containing:

- approved agent image digest and CLI version;
- promoted runtime class and runtime version;
- CPU, memory, PID, and temporary-storage ceilings;
- UID/GID, read-only root, capabilities, `no_new_privileges`, devices, mounts, and namespace settings;
- workspace mode and retention;
- network mode and egress policy;
- credential grants, expiry, and revocation behavior;
- maximum session duration and idle timeout.

Reject unknown policy versions and any request that attempts to override these fields. The browser and agent container cannot contact the Docker daemon or worker control API. The trusted worker agent receives only the resolved policy and an authenticated lifecycle request.

**Network gate:** do not advertise strict domain allowlisting while the TLS SNI/Host mismatch probe succeeds. Until an approved TLS-aware gateway or equivalent network policy passes that case, real session policies must use no egress or a separately reviewed restriction that does not claim hostname enforcement.

## Session lifecycle

```text
requested → queued → provisioning → ready → stopping → stopped
                 ↘ failed       ↘ failed       ↘ failed
ready → expired → stopping → stopped
```

- `requested`: request accepted and validated.
- `queued`: waiting for worker capacity.
- `provisioning`: workspace, credentials, network, and container are being prepared.
- `ready`: attach channel is available and health checks pass.
- `stopping`: teardown and revocation are in progress.
- `stopped`: resources are removed and retention policy is applied.
- `failed`: provisioning or runtime failed; safe failure reason and cleanup status are retained.
- `expired`: session lifetime ended; transitions to `stopping` automatically.

State changes are backend-owned. Stop is idempotent. The reconciler must converge resources to the declared state after worker restart or partial failure; a rejected or failed start must not leave an accessible container, live grant, or orphaned network.

## HTTP API contract (v1)

All endpoints require authenticated organization identity. Use JSON, TLS, request IDs, and an idempotency key for session creation.

### Create

`POST /v1/sessions` with `Idempotency-Key`:

```json
{
  "display_name": "codex-task-482",
  "policy_id": "codex-pilot-v1"
}
```

Return `202 Accepted` with `{ "id": "...", "state": "queued", "created_at": "..." }`. The server assigns owner, worker, image, runtime, limits, workspace, and network policy. Do not accept raw commands, image names, mount paths, environment maps, or Docker options from the client.

### List and inspect

- `GET /v1/sessions?state=&cursor=` returns only sessions visible to the caller, with pagination.
- `GET /v1/sessions/{id}` returns lifecycle state, safe policy summary, timestamps, and a sanitized failure code/detail.
- Do not return environment values, CLI auth material, raw prompts, or worker secrets.

### Attach

`POST /v1/sessions/{id}/attach-ticket` authorizes the owner/operator and returns a short-lived, single-use attach ticket plus a backend-proxied terminal URL. Ticket lifetime and single-use semantics are enforced server-side. No Docker socket, SSH key, or worker address is sent to the browser.

### Stop

`POST /v1/sessions/{id}/stop` requests idempotent teardown and returns the current state. Repeated stop calls return the same terminal outcome. Only the owner or an authorized operator can stop a session.

### Events

`GET /v1/sessions/{id}/events?cursor=` returns authorized, redacted lifecycle events. It excludes prompts, terminal contents, credentials, and arbitrary container logs unless a distinct audited support workflow explicitly permits them.

## Persisted records and audit

Minimum records:

- **Principal:** organization ID, subject ID, role mapping, identity-provider reference.
- **Policy:** immutable version, approved image/runtime digests, OCI limits, workspace/egress/credential policy, expiry, and approver.
- **Session:** opaque ID, owner, policy version, worker ID, state, workspace reference, created/ready/stopped times, expiry, idempotency key hash, and failure code.
- **Grant:** session ID, secret reference, scope, issued/expiry/revocation times; never persist the secret value in session metadata.
- **Audit event:** actor, action, target, result, time, request/correlation ID, policy version, and cleanup outcome.

Audit session creation, denial, attach-ticket issue/use, policy resolution, stop, expiry, grant issue/revoke, and cleanup failures. Redact secrets, tokens, prompts, and terminal output. Set retention for audit and workspace data separately.

## Initial acceptance criteria

1. A pilot user can create, attach, inspect, and stop a Codex session without manual Docker/Lima commands.
2. Member access to another user's session is denied for list, inspect, attach, and stop; operator access is auditable.
3. Client-supplied image/runtime/mount/network/privilege overrides are rejected; only a versioned approved policy can reach the worker.
4. A rejected or failed start leaves no running workload, reusable attach ticket, active grant, or orphaned temporary network.
5. Stop and expiry revoke session grants and clean temporary homes idempotently, including after worker restart.
6. Workspace data follows the selected retention policy and is not visible across users/sessions without an explicit shared-workspace grant.
7. Direct egress remains blocked. No strict hostname-policy claim is made until the SNI/Host mismatch is prevented and the regression case passes.
8. At five simultaneous sessions, request-to-ready p95 is below 25 seconds for the agreed cold/warm mix. Record attach-to-terminal-ready, first response, queue time, and cleanup separately from session startup.

## Decisions to close before implementation

| Decision | Proposed default for first pilot | Owner input needed |
| --- | --- | --- |
| Identity | Organization SSO; one organization | Which IdP and group/role source? |
| Runtime | One promoted runtime and immutable image digest | Promote stable gVisor only after network and security gates; otherwise specify approved runc baseline |
| Workspace | Per-user managed storage inside the VM, isolated from host files; preserve workspace across session stops | Retention duration and deletion/backup behavior still need a value |
| Platform login | Single local operator, loopback-only; add SSO before network exposure | Agreed for first pilot |
| Codex credentials | Current manual Codex device login in a session-only home; replace with brokered short-lived credentials later | Agreed as interim path based on prior decision |
| Network | Default deny; no strict host allowlist until TLS enforcement is proven | Which provider/source-control destinations are essential? |
| Session lifetime | Fixed maximum plus idle expiry | Maximum duration and idle timeout still need values |
| Capacity / speed | Queue above five concurrent sessions; request-to-ready p95 below 25 seconds | Agreed target; define cold/warm measurement mix |
| Wardyn | Complete requirement-to-evidence comparison before duplicating control-plane work | Who owns deployment/security acceptance? |

## Build sequence

1. Close the decisions above and complete the Wardyn fit assessment against this contract.
2. Resolve the network-policy gate and choose the exact pilot runtime/image policy.
3. Implement one authenticated backend-to-worker create/ready/attach/stop path with audit and cleanup.
4. Validate authorization, policy tampering, failures, cleanup, cross-session isolation, and egress through that API.
5. Connect the existing UI mock to the versioned API, replacing all demo status with backend state.
6. Add quotas, worker reconciliation, operations controls, and performance/pilot gates.

## Latest follow-up (2026-11-12)

The [five-session sandbox readiness results](SESSION_READINESS_RESULTS.md) record 50/50 successful cached-image starts per runtime. This is a no-network container/workspace/CLI smoke; full platform request-to-ready and uptime remain unmeasured. The [strict HTTPS egress enforcement plan](EGRESS_ENFORCEMENT_PLAN.md) specifies the proposed gateway and validation cases; the existing TLS tunnel gap remains open.

**TLS gateway candidate update (2026-11-12):** A separate TLS-terminating gateway passed 16 selected checks under each runtime, including the previously observed SNI mismatch and a decrypted HTTP Host mismatch. See [candidate results and remaining gates](TLS_GATEWAY_RESULTS.md). The default agent proxy is unchanged; full egress-policy acceptance remains open. A subsequent explicit HTTPS configuration completed three authenticated tasks without reconnect/error events; broader transport and failure testing remain open.

**Authenticated gateway follow-up (reviewed 2026-11-13):** Private ChatGPT login, one synthetic workspace-write task, incremental CLI events, cancellation, and cleanup passed. The initial run used fallback after WebSocket denials; the explicit HTTPS follow-up completed three tasks with zero error events. See [evidence and remaining checks](CODEX_TLS_AUTHENTICATED_RESULTS.md). This does not measure platform session-ready p95.

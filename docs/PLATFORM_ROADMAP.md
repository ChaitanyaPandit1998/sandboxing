# Agent Session Platform Roadmap

**Status:** Proposed. This is a delivery plan, not a statement that the platform capabilities below are implemented.

**UI prototype:** A static local dashboard mock now lives in [`../ui/prototype/`](../ui/prototype/) with run instructions in [`UI_PROTOTYPE.md`](UI_PROTOTYPE.md). Its session lifecycle is simulated; it is not the control plane and does not launch containers.

**Whiteboard requirement status:** See [`REQUIREMENTS_STATUS.md`](REQUIREMENTS_STATUS.md) for the current evidence matrix. The whiteboard calls for growth to 20 concurrent sessions, while the agreed first pilot starts at five. It also specifies p95 below 20 seconds, while the current pilot contract specifies below 25 seconds; resolve that target difference before acceptance.

## Goal

Provide organization-managed Codex sessions that start quickly, keep work isolated, constrain network and credential access, and leave an auditable record. The existing POC validates parts of the worker runtime and policy boundary; this roadmap adds the session-management product around it.

## Guiding decision

Evaluate Wardyn against the requirements before building equivalent control-plane features. Prefer integrating or extending it if the required behavior is present and acceptable for the organization's deployment and security review. Build only the gaps that remain. Wardyn is currently described by its project as pre-alpha, so verify the exact version and deployment rather than assuming every documented capability is production-ready.

## Initial scope

- Codex CLI sessions only.
- One local operator for the first pilot; loopback-only service. Add organization SSO before remote or multi-user access.
- One approved, digest-pinned agent image and one worker runtime policy.
- Five simultaneous sessions; target request-to-ready p95 below 25 seconds under an agreed cold/warm mix.
- Per-user managed workspaces persist across session stops; session homes and CLI credentials remain temporary for the initial pilot.
- Per-session resource limits, expiry, workspace retention, and cleanup.
- Default-deny direct egress. Strict hostname allowlisting remains a release gate because the current proxy permits a TLS hostname mismatch inside an allowed CONNECT tunnel.
- No long-lived provider or source-control secrets inside the image.
- Session create, attach, stop, inspect, and audit flows.

Claude Code, Kubernetes scheduling, warm pools, snapshot/resume, broad MCP support, and end-user policy authoring are out of the first milestone unless the pilot requirements make one essential.

## Milestones

### 0. Requirements and Wardyn fit assessment

**Work**

- Agree on user roles, session lifetime, expected concurrency, workspace retention, allowed destinations, credential needs, and startup target.
- Create a requirement-to-evidence matrix for Wardyn and the POC.
- In a disposable environment, run the same Codex image and security policy through Wardyn and the existing POC.
- Record whether Wardyn's selected confinement mode actually uses the runtime/version that passed the POC checks.

**Acceptance**

- Each requirement is marked demonstrated, missing, or not yet verified, with evidence and owner.
- The whiteboard requirement coverage is tracked in [`REQUIREMENTS_STATUS.md`](REQUIREMENTS_STATUS.md); resolve the latency-target difference and define the 20-session scale test.
- A written adopt, extend, or build decision identifies concrete gaps and operational constraints.

### 1. Control-plane contract

The draft v1 API, lifecycle, policy boundary, audit model, and acceptance criteria are in [`SESSION_CONTROL_PLANE_SPEC.md`](SESSION_CONTROL_PLANE_SPEC.md). Close its owner decisions and update the contract before wiring session creation to Docker. Minimum entities:

- **Principal:** user, team, and role.
- **Policy:** approved image digest, runtime class, resource limits, writable paths, egress rules, credential grants, expiry, and retention.
- **Session:** owner, policy version, worker, lifecycle state, workspace reference, timestamps, and failure reason.
- **Approval:** requesting session/action, approver, decision, scope, and expiry.
- **Audit event:** actor, action, target, outcome, timestamp, and correlation ID; redact secrets and sensitive prompt content.

**Acceptance**

- The API rejects unknown policies and requests the worker cannot enforce.
- Session state transitions and authorization rules are documented and versioned.

### 2. End-to-end single-session slice

Build one path from authenticated request to usable Codex session:

1. Authenticate the user and authorize session creation.
2. Resolve a fixed approved policy and assign an eligible worker.
3. Provision an isolated workspace and short-lived session home.
4. Start the agent container with the approved runtime, non-root identity, resource limits, read-only root, no extra capabilities, and controlled egress.
5. Return an attach handle without exposing Docker or worker credentials.
6. Stop or expire the session, revoke session grants, clean temporary state, and retain or delete workspace data according to policy.
7. Write lifecycle events to the audit store.

**Acceptance**

- A pilot user can create, attach, inspect, and stop a session without manual Docker/Lima commands.
- A rejected start leaves no running container or leaked temporary credential.
- Cleanup is idempotent and completes after normal stop, timeout, and worker restart.

### 3. Credential brokering and approval flow

- Keep provider and Git credentials outside images, workspaces, shell history, and logs.
- Begin with narrowly scoped, short-lived credentials or proxy-side injection.
- Route external traffic through the policy-enforcing proxy; deny direct egress.
- Add approval for explicitly defined exceptional actions, with clear expiry and audit trail.

**Acceptance**

- A session receives only its declared grant; another session cannot use it.
- Grants expire or are revoked at session end, including failure cleanup.
- Unlisted destinations and direct network paths remain denied; approval cannot silently widen other policy fields.

### 4. Multi-user operations

- Add organization/team membership and roles (member, approver, operator, administrator).
- Enforce per-user/team session and resource quotas.
- Add worker health, capacity tracking, retries, expiry sweeps, and orphan cleanup.
- Provide an operator view of active, failed, and recently completed sessions.

**Acceptance**

- Cross-user session inspection/attach is denied unless explicitly authorized.
- Quota limits are enforced during concurrent start requests.
- Operators can trace a failed session and recover capacity without editing container state by hand.

### 5. Security and compatibility validation

Run the existing runtime and proxy checks through the full control-plane path, then add tests for API authorization, policy tampering, credential revocation, approval expiry, workspace retention, cleanup after crashes, and concurrent starts. Keep results tied to the exact image digest, runtime build, worker kernel, policy, and test revision.

Use [AGENT_SESSION_VALIDATION_PLAN.md](AGENT_SESSION_VALIDATION_PLAN.md) for agent/runtime coverage and [SECURITY_VALIDATION_PLAN.md](SECURITY_VALIDATION_PLAN.md) for the broader threat-driven matrix. A passing suite is evidence for those tested cases; it is not a security certification.

**Acceptance**

- Critical isolation, egress, authorization, cross-session, and cleanup cases pass with negative controls.
- Every exception has a documented risk owner and remediation decision.
- Runtime upgrades rerun the relevant suite before promotion.

### 6. Performance and pilot gate

Measure request-to-session-ready, attach-to-terminal-ready, first model response, queue time, and cleanup separately. Test warm and cold worker paths and expected concurrency. Report p50, p95, failures, CPU, and peak memory; include provider latency separately from sandbox startup.

**Acceptance**

- Product owner sets numeric latency and capacity targets before testing.
- At expected concurrency, measured results meet targets or trigger a specific scaling/warm-pool decision.
- A small pilot has an owner, rollback path, support procedure, and review date.

## Immediate sequence

1. Preserve the agreed pilot scope: local single-operator access, managed per-user workspace persistence, five concurrent sessions, and request-to-ready p95 below 25 seconds. Resolve the stricter whiteboard p95-below-20-seconds target and define when the scale target grows to 20. Set the remaining workspace-retention, session-lifetime, and cold/warm measurement details.
2. Complete Milestone 0 using the current Codex image and POC regression suite; finish Wardyn checks for persistent workspace behavior, Codex device-login compatibility, cleanup/recovery, and performance before deciding whether to adopt, extend, or build.
3. Resolve the strict-egress gap and choose the exact runtime/image policy for the pilot. Keep the initial service loopback-only until SSO and multi-user authorization exist.
4. Implement one authenticated create/ready/attach/stop backend slice with cleanup and audit; connect the UI after this API is stable.

The UI mock can guide feedback on the operator workflow while the control-plane contract is designed. Connect it to real lifecycle APIs only after authorization, policy enforcement, egress, audit, and cleanup behavior are defined.

## Current evidence to carry forward

The POC has successful targeted `runsc-next` regressions recorded in [`../results/agent-session-20261112/runsc-next-regression-summary.json`](../results/agent-session-20261112/runsc-next-regression-summary.json). The tested nightly is a candidate build, not the pinned stable runtime. Existing startup timings are CLI process-start measurements, not complete session-ready latency. Preserve these limits in any platform comparison.

## Latest follow-up (2026-11-12)

The [five-session sandbox readiness results](SESSION_READINESS_RESULTS.md) record 50/50 successful cached-image starts per runtime. This is a no-network container/workspace/CLI smoke; full platform request-to-ready and uptime remain unmeasured. The [strict HTTPS egress enforcement plan](EGRESS_ENFORCEMENT_PLAN.md) specifies the proposed gateway and validation cases; the existing TLS tunnel gap remains open.

**TLS gateway candidate update (2026-11-12):** A separate TLS-terminating gateway passed 16 selected checks under each runtime, including the previously observed SNI mismatch and a decrypted HTTP Host mismatch. See [candidate results and remaining gates](TLS_GATEWAY_RESULTS.md). The default agent proxy is unchanged; full egress-policy and authenticated Codex acceptance remain open.

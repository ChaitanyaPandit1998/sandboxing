# Agent Session Platform Roadmap

**Status:** Proposed. This is a delivery plan, not a statement that the platform capabilities below are implemented.

## Goal

Provide organization-managed Codex sessions that start quickly, keep work isolated, constrain network and credential access, and leave an auditable record. The existing POC validates parts of the worker runtime and policy boundary; this roadmap adds the session-management product around it.

## Guiding decision

Evaluate Wardyn against the requirements before building equivalent control-plane features. Prefer integrating or extending it if the required behavior is present and acceptable for the organization's deployment and security review. Build only the gaps that remain. Wardyn is currently described by its project as pre-alpha, so verify the exact version and deployment rather than assuming every documented capability is production-ready.

## Initial scope

- Codex CLI sessions only.
- One organization and a small pilot group.
- One approved, digest-pinned agent image and one worker runtime policy.
- Per-session resource limits, workspace, expiry, and cleanup.
- Default-deny network access through the existing allowlist proxy path.
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
- A written adopt, extend, or build decision identifies concrete gaps and operational constraints.

### 1. Control-plane contract

Define the API and persisted records before wiring session creation to Docker. Minimum entities:

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

1. Agree on initial scope and measurable pilot targets.
2. Complete Milestone 0 using the current Codex image and the POC regression suite.
3. Decide whether to adopt, extend, or build before implementing duplicate identity, approval, audit, or workspace features.
4. Deliver Milestone 2 as the first code milestone; defer broadening the agent/runtime matrix until that path is repeatable.

## Current evidence to carry forward

The POC has successful targeted `runsc-next` regressions recorded in [`../results/agent-session-20261112/runsc-next-regression-summary.json`](../results/agent-session-20261112/runsc-next-regression-summary.json). The tested nightly is a candidate build, not the pinned stable runtime. Existing startup timings are CLI process-start measurements, not complete session-ready latency. Preserve these limits in any platform comparison.

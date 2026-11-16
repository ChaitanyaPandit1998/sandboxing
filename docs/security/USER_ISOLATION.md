# Owner-scoped sessions and workspace isolation

**Status (2026-11-14):** Ownership/storage boundaries and member/operator checks are implemented and tested. **An optional Okta OIDC candidate is implemented and simulated-provider tested; real tenant authentication remains unverified.** The console remains a trusted local-operator pilot; do not expose it remotely or to mutually untrusted users. Real Okta configuration, distinct-user acceptance and secure attach are still required before multi-user deployment.

## Identity boundary

In default personal mode, the trusted operator binds a principal and role when starting the loopback server. The browser cannot set or change them through headers, request JSON or session identifiers. `/api/identity` reports the binding and explicitly reports `organization_sso: false`. It does not authenticate a person. Other processes/users on the same Mac can reach bootstrap, and the local operator already has Docker access; these are not defenses against that operator.

For an **isolated local validation**, an operator can select a principal using `--principal member-a`; this defaults to `member`. `--role operator` must be explicitly selected for elevated access. With no options, the existing `local-pilot` operator behavior remains unchanged. The worker CLI follows the same default. Principal IDs accept only bounded lowercase ASCII letters, digits, dots, underscores and hyphens; names do not become filesystem paths.

Never use a user-controlled header/body as the authority for these flags. The optional Okta candidate derives principal/role from verified issuer/subject and explicit assignments, then uses a request-local immutable worker adapter. Its browser sessions and local assignment revocation are simulated-provider tested; real tenant login, provider-side revocation, organization tenancy and remote transport remain open. See [authentication modes](AUTHENTICATION.md).

## Permissions

| Operation | Member | Operator |
|---|---|---|
| Create | Own sessions, approved fixed policy | Own sessions, approved fixed policy |
| List / inspect / events | Own sessions only | Sessions in this configured worker state |
| Stop | Own sessions only | Sessions in this configured worker state |
| Login / attach command | Own session only | Own session only; cannot use another owner's credentials |
| Monitoring / history / alerts / alert audit | Own sessions only | All sessions and worker-level signals |
| Acknowledge / resolve | Own session alerts only | All alerts, including worker-level signals |
| Resident security collection | Not permitted | Permitted |

Unauthorized cross-owner session/alert access returns not-found rather than revealing metadata. Credential-bearing attach is separately owner-checked, including after terminal handoff. Denials are recorded in the private `authorization_audit` table with bounded actor/action/target metadata. That table currently has no UI reader; centralized/tamper-resistant authorization audit is pending. Alert state actions record the bound principal; the historical local operator label is retained for the default pilot.

The operator can inspect or stop another owner's session but cannot attach/login as that owner through the managed interface. A trusted Docker operator can bypass this CLI boundary directly; production users must never receive Docker/worker host access or rely on editable terminal commands as an authorization channel. The secure browser attach relay remains a separate required feature.

## Storage and quotas

- Session rows store an owner. Legacy rows become `local-pilot`, without changing their deadlines or moving workspace files.
- The existing `local-pilot` workspace keeps its original Docker volume name and contents. Legacy pilot sharing is preserved; data is not copied into new owners' volumes.
- New owners receive separate volumes derived from a bounded hash of their principal. Containers mount only that owner's workspace plus their own public CA. Resources carry worker/session labels and a hashed owner label; mismatches are rejected before cleanup.
- Session homes and gateway keys remain temporary and separate per session. Same-owner replacement keeps workspace data but starts with a new home. No Codex credentials are copied between users or sessions.
- Idempotency keys are scoped by owner. The same key from two owners creates separate sessions, while retrying within one owner returns the original result/deadline.
- Member quota is two active/reserved sessions. The shared worker limit remains five across owners; ready/provisioning/stopping reservations count. Default operator pilot behavior still allows five. These are pilot limits, not organization-wide quota management.
- Member reconciliation touches only that owner's sessions. The resident operator reconciler handles expiry and cleanup across owners. Workspace retention/deletion, byte quotas, backups and general multi-tenant threat acceptance remain open.

Monitoring, event history, alert counts and action trails are filtered by session ownership. Members do not receive other owners' records or worker-wide alert/error counts. Shared policy/rule metadata and generic collector health remain visible. The UI shows the bound identity/role, appropriate session limit and session owner; credential actions are disabled for foreign-owner rows and enforced again by the API/worker.

## Validation

Six ownership unit tests cover scoped access, denial audit, owner-scoped idempotency, member/global quotas, volume and owner-label checks, history/alert/audit/monitor filtering, member reconciliation, implicit member defaults and legacy migration. The local API suite passed 18 tests, with one separate live lifecycle test skipped.

A separate VM state and three real loopback APIs (two members and an operator) passed **19 workflow checks**: forged identity headers and owner overrides rejected, guessed foreign IDs denied, role-restricted terminal handoff, separate workspace/home markers, same-owner persistence, scoped history/alert/monitor data, foreign-alert mutation denial, operator expiry/stop across owners and cleanup. Test containers, networks, volumes and state were removed. This used **trusted simulated principals**, not real users or SSO.

The original managed-worker suite also passed **22 checks**, including legacy storage/deadlines, five-session capacity, expiry, recovery, gateway probes and cleanup. A private metadata backup was made before the additive production migration; the real pilot's 13 existing sessions retained `local-pilot` ownership. Browser/API review verified identity display, default quota, monitoring and alerts with no browser errors. [Evidence](../../results/user-isolation-20261114/).

No new device login/model task, cross-kernel exploit test, organization identity, remote access or production multi-user security claim is established here. Next connect verified SSO identities to this ownership boundary, replace privileged terminal handoff for real users, and run authenticated distinct-user acceptance tests.

## Authentication modes follow-up (2026-11-14)

Personal mode remains the default. Optional Okta code/PKCE login, signature/OIDC validation, opaque browser sessions, per-request identities and assignment/role reload are implemented and tested using a simulated provider. Okta bootstrap cannot grant local operator authority, and the privileged Mac-terminal handoff is disabled in that mode. Real tenant configuration/login, actual distinct-user resource acceptance, provider-side revocation and secure attach remain open. [Authentication contract and evidence](AUTHENTICATION.md).


**Personal browser terminal (2026-11-15):** Local terminal tickets/channels now enforce exact owner and browser binding; even an operator cannot attach to another owner's credentials. Revalidation, bounded input/output, fixed worker commands and disconnect/stop cleanup are exercised. This is a trusted personal-mode pilot; Okta-mode relay access remains disabled and organization/remote acceptance is pending. [Runbook](../runbooks/LOCAL_CONSOLE.md#browser-terminal-for-the-local-personal-pilot-2026-11-15).

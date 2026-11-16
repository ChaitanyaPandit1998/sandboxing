# Development log

Changes are recorded newest first. All timestamps use **Asia/Kolkata (IST, UTC+05:30)**.

## 2026-11-16T19:07:18+05:30 — Prepare the integrated pilot batch for commit and push

- **Docs:** Synchronized root README, executive/POC summaries, static prototype pointer, authentication description, roadmap and current storage/runbook requirements. Personal browser terminal acceptance and actual 5 GiB migration are current; organization identity, full reboot and sustained performance remain open. Earlier dated entries retain their historical status.
- **Verification:** Local discovery ran 177 tests: 154 passed / 23 skipped (optional OIDC dependencies unavailable and explicit live tests disabled). The initial restricted run failed to bind localhost HTTP fixtures; the authorized rerun with socket access passed. No fresh provider/model/login or destructive storage tests were needed. Previously recorded 16 migration / 22 quota checks remain the live evidence.
- **State:** Commit/push requested by the user; this entry records preparation, not an observed successful push. Commit identity and push result will be reported after Git completes. Existing accumulated pilot changes and sanitized evidence are included; runtime credentials/state remain excluded.
- **Next:** Verify remote commit identity after pushing, then run repeated five-session readiness and uptime/recovery acceptance. Retain the actual rollback copy until workspace acceptance.


## 2026-11-16T18:29:45+05:30 — Migrate the pilot workspace to enforced quota storage

- **Successful:** Implemented trusted-operator verified copy/cutover/rollback/abort/finalize commands, private migration records/audit, root-owned source/target identity checks and deletion guards while recovery copies remain. Dynamic owner-volume lookup prevents stale worker/reconciler bindings. The actual pilot's 11 entries / 3,765 logical bytes matched after copying, a managed session verified workspace access and was stopped, and the active backend reports a hard 5 GiB quota with zero active sessions. Original ordinary volume retained; actual backup finalization not performed.
- **Validation:** 123 affected tests passed / one skipped; 16 disposable migration checks and 22 repeat managed-quota checks passed. Browser verified hard quota/remaining capacity and retained-copy deletion refusal with zero console errors. Seven deployed root/worker source hashes matched the repository; both services active. Final Python/shell/JavaScript syntax, documentation-link and diff checks passed. [Deployment verification](results/workspace-migration-20261116/deployment.json). No model requests or temporary authentication-home access. [Actual cutover](results/workspace-migration-20261116/pilot-cutover.json), [migration canary](results/workspace-migration-20261116/live.json), [quota regression](results/workspace-migration-20261116/existing-quota-regression.json), [tests](results/workspace-migration-20261116/regressions.json).
- **Failed / corrected:** Initial unit setup lacked the new imported module; a Mac-only absence of `os.listxattr` needed a test-only syscall mock (Linux live uses the actual syscall). Addressed stale cached volume binding and migrated-alias recreation. No remaining failures in these recorded suites. Copier conservatively rejects xattrs/ACLs/special files and modified snapshots; rollback never merges newer work.
- **Docs / state:** Updated current storage, requirements, roadmap and console documentation; added [migration/recovery runbook](docs/runbooks/WORKSPACE_MIGRATION.md). Historical pre-migration evidence retained. Uncommitted/unpushed; unrelated work preserved.
- **Remaining / next:** Accept the migrated workspace before explicitly deleting its rollback copy. Then measure five-session readiness and sustained uptime/recovery. Full VM reboot/crash recovery, inode exhaustion, large migrations/exports and organization identities remain open.


## 2026-11-16T00:40:13+05:30 — Read-only status check after interrupted turns

- **Verified now:** Lima VM running; user reconciler and root quota mount service active; local console returned HTTP 200 on port 4180; no running Docker containers. Legacy workspace remains retained at 22,528 allocated bytes, zero active sessions, no deletion audit and advisory 5 GiB budget. Root quota status for local-pilot remains absent, consistent with no enrollment/migration.
- **Recorded evidence:** Reviewed the last quota integration results: 106 tests passed / one skipped and 22 live checks passed. These suites were not rerun during this status check.
- **State / remaining:** Implementation changes remain uncommitted/unpushed. No provisioning, migration, session creation or data cutover performed by this check. Only this log was updated.
- **Next:** Prepare the verified migration/copy/cutover/rollback workflow; retain rollback data before enrolling the existing owner, then measure five-session readiness and uptime/recovery.


## 2026-11-15T13:27:00+05:30 — Integrate opt-in managed 5 GiB quotas

- **Successful:** Added a root-owned storage helper/manifest registry and boot mount service with serialized provisioning, 6 GiB guest-space reservation per owner, 4 GiB guest headroom and a 5 GiB XFS project cap. Formatting preserves allocation; live validation refuses lost reservations. Trusted operator enrollment is private and explicit. Worker create/attach/usage/export/delete verify ownership, UUID, mount, quota settings/inheritance and volume identity; no ordinary-volume fallback. Quota-aware confirmed deletion removes backing image/mount/metadata and leaves interrupted operations non-ready. UI shows verified hard quota/remaining space or legacy advisory state. Installed helper/service, registered only the actual worker namespace, and verified six deployed source hashes. No root-filesystem/fstab/sudoers changes or actual-user enrollment/migration.
- **Validation:** 106 tests passed / one opt-in live case skipped, including 25 new adapter/service cases. A real new-owner canary passed 22 checks: two-session aggregate 5 GiB limit, cross-owner denial, changed-limit/missing-mount refusal, export, write recovery, injected expiry retention, service remount recovery, backing-data deletion/audit and stale-identity denial. Four creates took 0.947, 0.835, 0.786, 0.815 seconds; this is not p95 or authenticated readiness. Browser verified quota/remaining fields and refresh with no errors. Zero model requests; disposable volumes, loops, manifests, registrations, state and temporary console removed. [Canary](results/workspace-quota-integration-20261115/live.json), [regressions](results/workspace-quota-integration-20261115/regressions.json), [deployment](results/workspace-quota-integration-20261115/deployment.json), [legacy unchanged](results/workspace-quota-integration-20261115/legacy-pilot.json). Compile/shell/JS syntax/diff/link checks passed.
- **Failed / corrected:** New tests exposed a dangling-config symlink fallback and malformed/negative quota snapshots; corrected and rerun. Added a failing lost-reservation regression and made the backend check actual allocated image blocks before loop access. A separate disposable 512 MiB test confirmed formatting retains allocation on this VM; explicit -K also preserves that intent. Unit installation emitted unrelated existing XFS scrub CPUAccounting deprecation warnings; verification succeeded. No managed canary failures remained.
- **Remaining:** Actual local-pilot volume remains advisory and unchanged. Existing-data migration/rollback, full VM reboot/crash recovery, inode exhaustion, larger exports, real organization identities, five-session p95 and sustained availability remain pending. Backend checks are per operation, not a continuous privileged-drift watchdog. Incomplete provisioning/deletion requires operator review; no blind recreate/force cleanup.
- **State:** Uncommitted and not pushed. Root helper/mount-recovery service deployed and enabled; opt-in worker/UI support deployed; no actual user enrolled. Existing unrelated changes preserved.
- **Next:** Prepare a verified existing-owner migration/copy/cutover/rollback workflow, retain rollback data, then validate five-session readiness and soak/recovery. [Current quota runbook](docs/platform/WORKSPACE_QUOTAS.md).


## 2026-11-15T11:46:54+05:30 — Validate a full-size 5 GiB quota backend candidate

- **Successful:** Inspected VM ext4 flags/storage/tooling read-only and selected a separate XFS project-quota candidate. Added an opt-in/root/VM/free-space guarded disposable test; no worker-state imports, user-data migration, root filesystem/fstab/sudoers edits or persistent service install. Final real-gVisor test passed all 16 checks at 5 GiB, including allocated-block readback, actual boundary writes, independent projects under UID 10001, space recovery, persisted limits/data/enforcement after remount and cleanup. [Live evidence](results/workspace-quota-20261115/live.json).
- **Validation:** 36 workspace tests passed, including seven new guard/readback cases. Compile and diff checks passed. Independent inventory found no test volumes, containers, loop devices or directories. [Existing pilot](results/workspace-quota-20261115/pilot-storage.json) remains retained with advisory quota. No HTTP/model/terminal tests repeated: service/session behavior was unchanged.
- **Failed / corrected:** Initial readback assumed project-ID rows and omitted zero-usage verbosity. Shell child helpers hit ENOMEM at 128 MiB; direct processes passed. Host and gVisor both returned ENOSPC; a strict EDQUOT assertion was wrong for XFS project quotas, confirmed against kernel source and readback/capacity/independent-project checks. Preserved [initial](results/workspace-quota-20261115/initial-live-failure.json), [diagnostic](results/workspace-quota-20261115/diagnostic.json) and [errno](results/workspace-quota-20261115/host-errno-diagnostic.json) results. All attempts cleaned their disposable storage.
- **Limits:** Candidate-only, not live pilot hard quota enforcement. Manual remount is not VM reboot/recovery acceptance; inode exhaustion, real-session use, backup/rollback and pool capacity admission remain pending. Runtime timing is test duration, not storage throughput or session readiness. No user workspace read or changed by the experiment.
- **State:** Uncommitted; not pushed. Current service/UI unchanged. [Design, sources and integration gates](docs/platform/WORKSPACE_QUOTAS.md) added; canonical docs updated without marking requirements complete.
- **Next:** Root-owned storage service/manifest and fail-closed worker lifecycle integration, including backing-data deletion; then new-owner canary, reviewed existing-data migration, five-session readiness and soak/recovery gates.


## 2026-11-15T02:27:10+05:30 — Owner-confirmed workspace deletion and audit

- **Successful:** Added owner-only prepare/delete API/CLI operations and a typed-confirmation dialog. Consent expires after 60 seconds, is single-use and tied to current volume identity. The lifecycle lock and repeated ownership/idle/lifetime checks block stale consent, active sessions and container references. No force removal. Token consumption and requested audit commit precede Docker removal; successful volume listing verifies absence. Recent owner-scoped outcomes appear in the storage UI. The additive token table retains hashes only. Installed three worker files with backups/equality checks and restarted the personal console.
- **Validation:** 74 passed / one opt-in live test skipped across deletion/storage/export/HTTP/ownership/terminal suites; twelve deletion cases include real CLI errors, audit-write failure and expiry during Docker inspection. Eight real-VM checks passed. Browser partial/exact phrase and Cancel checks passed; no final deletion click. Authenticated HTTP tests deleted only disposable data and verified absence, audit and replay denial. Temporary test console/volume/state removed; actual workspace retained with no deletion audit. [Evidence](results/workspace-deletion-20261115/regressions.json), [live](results/workspace-deletion-20261115/live.json), [HTTP/browser](results/workspace-deletion-20261115/http-browser.json), [actual workspace](results/workspace-deletion-20261115/personal-workspace.json).
- **Failed / corrected:** Initial module tests failed before implementation. Real HTTP replay failed its error contract although fixture deletion/audit succeeded: CLI main and helper import loaded distinct WorkerError classes. Added a failing subprocess regression, registered the CLI module under its import name, reran the suite and verified HTTP replay returns 409. [Failure record](results/workspace-deletion-20261115/initial-http-failure.json). Reviewed and adjusted dialog spacing/danger styling.
- **Limits:** Permanent volume removal has no automatic backup/undo or secure-erasure claim. A host-admin race is outside the managed lock. Uncertain outcomes are audited; a crash may leave requested. Audit retention policy, hard quota enforcement, large exports and organization acceptance remain pending.
- **State:** Uncommitted; no push performed. Existing unrelated changes preserved; no user workspace or credentials deleted/read by the deletion tests.
- **Next:** Select and test storage that enforces 5 GiB during writes; then five-session readiness and soak/recovery gates.


## 2026-11-15T02:05:39+05:30 — Bounded owner-only workspace export

- **Successful:** Added an authenticated CSRF-protected POST download endpoint, owner-bound worker command and workspace UI download action. Export holds the lifecycle lock and rejects active sessions/running volume consumers. A read-only/non-networked pinned runsc tar probe produces an archive bounded to 16 MiB / 10,000 entries / 30 seconds; unsafe entry types/paths and incomplete exports are rejected before download. No extraction, retained service archive or transcript logging. Installed three worker files with private backups/source equality checks and restarted the existing personal console.
- **Validation:** Tests failed for the expected missing module before implementation, then passed. Combined suite: 61 passed / one opt-in live case skipped. Nine export unit cases include actual subprocess size/timeout checks. Seven isolated real-VM checks passed. Browser downloaded a disposable fixture; verified contents without extraction, then removed its download, volume/state and temporary console. No browser errors or export probes remained. [Regressions](results/workspace-export-20261115/regressions.json), [live](results/workspace-export-20261115/live.json), [browser](results/workspace-export-20261115/browser.json), [deployment](results/workspace-export-20261115/deployment.json). Syntax/compile/diff checks passed.
- **Limits:** Export is intentionally smaller than the advisory 5 GiB storage budget; larger exports need bounded streaming. Symlinks/hard links/special or unsupported filenames reject the whole archive. User-stored secrets in the workspace are included; temporary login homes are excluded. Host-admin writes are outside the worker lock. Actual user workspace/credentials were not read by export validation.
- **State:** Uncommitted; no push performed. Existing unrelated changes preserved.
- **Next:** Owner-confirmed deletion with active-session protection and an audit record; hard quota backend and five-session readiness/soak gates remain pending.


## 2026-11-15T01:19:11+05:30 — Owner-scoped workspace storage visibility

- **Successful:** Added the worker workspace metadata command, authenticated GET endpoint and console panel. User selected a 5 GiB per-user advisory budget. Ownership checks forbid foreign-volume access; no request-supplied owner/path. Read-only, network-disabled UID 10001 probes return metadata only; missing workspaces are not created. Installed the two worker files with source equality checks and restarted the existing personal console.
- **Validation:** Eight new unit cases; combined suite 51 passed / one opt-in live case skipped. Eight isolated real-VM checks passed, including unreadable-as-unknown, unchanged fixture data and cleanup. Actual retained workspace measured 22,528 bytes; browser refresh passed with no console errors. Syntax/compile and diff checks passed. [Evidence](results/workspace-storage-20261115/live.json), [regressions](results/workspace-storage-20261115/regressions.json), [deployment](results/workspace-storage-20261115/deployed.json).
- **Failed / corrected:** Initial tests failed before the helper existed. Initial real Node child-process probe failed with ENOMEM at 128/256 MiB; direct du as PID 1 passed at the original 128 MiB limit. Preserved [initial failure](results/workspace-storage-20261115/initial-live-failure.json). Restricted process/loopback checks required approved local escalation. Interrupted startup had no surviving listener; restarted and verified the endpoint/browser.
- **Remaining:** Usage is allocated/readable metadata, KiB-granular and non-atomic. Budget is advisory, not a hard quota; exports, confirmed deletion and retention automation are not implemented. No credentials read or copied.
- **State:** Uncommitted; no push performed. Existing unrelated changes preserved. Updated runbook, roadmap, requirements and stale browser-attach statements in the MVP contract.
- **Next:** Implement reviewed owner-only export and confirmed deletion with active-session protection; select write-enforcing storage for hard quotas, then run five-session readiness/soak gates.


## 2026-11-15T00:46:28+05:30 — Authenticated browser coding acceptance passed

- **Successful:** Verified CLI login status without credential inspection in user-signed-in session `9f23bb2fde2f44ed9f830919e8b012da` (the user created/signed into that session, rather than the initial `b090f454` preparation). Submitted a bounded synthetic Node task through the embedded browser terminal. Eight generated tests and 11 independently authored edge checks passed. Disconnect left zero Codex CLI processes; reopen retained both file hashes. UI stop removed both test sessions’ containers/networks and tmpfs login homes; a temporary read-only/network-disabled probe verified retained hashes after stop. [Evidence](results/browser-acceptance-20261115/status.json).
- **Corrected:** Accessibility click failed; current DOM locators worked. Sequential prompt typing timed out after partial input; the unsent draft was cleared and the full synthetic prompt pasted once, then submitted. An early filesystem poll preceded file creation; subsequent checks passed after task completion.
- **Remaining:** One local task is not concurrency/performance/uptime/security acceptance. Okta remains deferred. Synthetic files remain only in the managed persistent workspace. No credentials or private login transcript saved.
- **State:** No application code changes; docs/evidence updated, uncommitted and not pushed.
- **Next:** Workspace visibility and lifecycle controls, then five-session readiness and soak/recovery gates.


## 2026-11-15T00:39:17+05:30 — Prepare authenticated browser acceptance

- **Successful:** Verified the actual resident worker is active/nonstale and historical sessions are stopped. Created session `b090f4541c21432f95c5249ddcc01fb7` through the personal browser console; worker confirms fixed runsc runtime, login-ready state and one-hour expiry. [Pending acceptance status](results/browser-acceptance-20261115/status.json).
- **Failed / corrected:** Restricted shell could not reach loopback. A second console startup then found port 4180 occupied; existing listener and browser were verified rather than replacing the running service. Chrome connector was unavailable; the existing in-app browser console worked.
- **Remaining:** User private Codex login, model coding task, independent correctness checks, reconnect/persistence and final cleanup acceptance. No credentials or terminal login transcript were recorded; no model request made.
- **State:** Application source unchanged; evidence and log uncommitted. Session intentionally retained pending private sign-in, with normal one-hour expiry.
- **Next:** After private login, execute the bounded coding acceptance workflow and record actual results. Okta remains deferred.


## 2026-11-15T00:36:36+05:30 — Next-step review and terminal regression check

- **Reviewed:** Task-specific security/concurrency/review guidance, current requirements and roadmap, recorded browser-terminal evidence, and relay ownership/ticket/capacity/cleanup paths. This was a focused inspection, not a complete pending-diff audit.
- **Validation:** `python3 -m unittest discover -s tests -p 'test_terminal_relay.py' -q`: 18 tests passed after rerun with loopback access. The first restricted execution had five HTTP setup errors (`PermissionError` binding local sockets); it did not establish assertion failures.
- **Remaining:** Authenticated browser coding-task acceptance, workspace lifecycle controls, five-session end-to-end readiness measurements, soak/recovery validation, and deferred real Okta acceptance. Existing earlier live evidence was read, not rerun.
- **State:** No application code changed; work remains uncommitted and not pushed.
- **Next:** Validate an authenticated browser coding workflow, then implement workspace visibility and storage/lifecycle controls in small tested increments.


## 2026-11-15T00:33:59+05:30 — Adopt repository coding skills

- **Changed:** Reviewed the user-provided local bundle and installed 15 instruction-only skills under `.agents/skills/`. Added task-specific routing to [AGENTS.md](AGENTS.md) while preserving development-log rules, and linked it from the documentation index. Global Codex settings were not changed.
- **Validation:** All 15 installed manifests match the originals byte-for-byte and their recorded SHA-256 hashes; metadata, routing coverage, and local skill links passed checks. `git diff --check` passed. [Installation manifest](results/skill-adoption-20261115/installed.json).
- **Failed / remaining:** No setup check failed. Runtime tests were not run for this instruction-only batch. Automatic discovery in a fresh repository session has not been observed; this adoption does not constitute a review of the existing pending application changes.
- **State:** Uncommitted and not pushed; existing pending work preserved.
- **Next:** Apply the relevant security, concurrency, testing, and review skills when reviewing the pending browser-terminal and session lifecycle changes.


Historical commit timestamps below are exact Git **author timestamps**, not test execution or push times. Entries marked **date only** have no independently recorded wall-clock execution time; no time has been invented. Entries without an explicit SHA may refer to the consolidation commit that contains them; use Git history for its exact ID. Relative test timings measure durations, not time of day.







## 2026-11-15T00:22:57+05:30 — Personal-mode browser PTY terminal and tracked cleanup

- **Changed:** Added owner/browser-bound 30-second one-use hashed tickets; bounded memory-only HTTP/PTY input/output, resize, deadline/heartbeat expiry, per-session/global capacity reservations and cleanup retries. The browser selects only fixed Codex login/attach modes. Worker rechecks owner/container labels, runs a tracked in-container Node wrapper and closes only matching PID/start-time/relay arguments; cancellation markers prevent late startup after immediate disconnect. Added safe controlling-TTY exec helper and an SSH wrapper disabling escapes, local command mode, forwarding and ambient provider-key inheritance. User-facing xterm.js modal replaces copied-command login/attach in personal mode; legacy fallback remains and Okta relay stays disabled.
- **Validation:** Eighteen terminal unit/real host PTY/local HTTP tests, 18 existing API regressions, six ownership tests, twelve profile tests and twenty OIDC regressions passed; one isolated real VM/HTTP/PTY test passed 13 workflow checks. One separate legacy live API test skipped. Actual runsc candidate rendered Codex's sign-in UI, resized, reaped host/remote Codex processes on explicit and immediate close, retained workspace contents, revoked on Stop and retained the volume before removing only disposable test resources. Deadline expiry used injection; no one-hour wait. [Evidence](results/browser-terminal-20261115/).
- **Browser / fixes:** Browser Create/Open Codex/arrow-key selection/Disconnect/panel close/Stop passed with zero browser console errors. Preview saved to /private/tmp/sandbox-browser-terminal.png. Initial PTY test found process-group signalling cleanup failure; changed to PTY HUP/direct child reaping plus independent tracked remote cleanup. Real browser testing then exposed cookie-name collisions across localhost ports; now cookies are port-scoped, with added regression coverage and no Origin/CSRF bypass. A browser Stop click timed out while its confirmation ran; inspected current dialog/state and verified the stopped result instead of repeating the action. Temporary diagnostics used only booleans and were removed.
- **Dependencies / deployment:** Vendored pinned official npm xterm.js 6.0.0 and fit addon 0.11.0 with published archive integrity, local file hashes and MIT licenses; no package scripts/CDN. Backed up the prior VM worker privately, installed only tested worker/helper files and verified source hashes/resident health. Main console restarted in personal mode at 127.0.0.1:4180; isolated preview/states/containers/networks/test volumes removed. Persistent pilot workspace preserved. JS/shell/Node-program syntax, Python AST, DOM IDs, document links, vendor integrity and Git whitespace checked.
- **Scope / limits:** Real Codex device login and a model task through the browser are not yet validated. Okta remains explicitly deferred. No remote/org terminal exposure, transcript persistence, production multi-user claim, new perf-p95 or uptime claim. Ticket-issue/use durable auditing, remote HTTPS, organization auth coupling, five-terminal load and broad failure/soak acceptance remain open. Failed cleanup retains capacity and retries; host/VM outage can delay remote teardown. Closed channels retain a short-lived bounded in-memory final output only; private terminal bytes are not written to logs or SQLite.
- **State / next:** Local browser terminal deployed and docs/requirements/roadmap updated; all changes uncommitted/unpushed. Reload the console to use New session → Login/Open Codex. Next privately validate the authenticated browser task, then implement workspace storage/retention/export/deletion controls and continue remaining security/performance gates.


## 2026-11-14T16:45:40+05:30 — Defer Okta troubleshooting and restore the personal pilot

- **User decision:** Set authentication work aside and prioritize the remaining sandbox functionality. Real Okta login remains unverified after the user's missing-passkey enrollment/sign-in prompt; the implementation and external temporary public configuration are retained for later.
- **Changed:** Verified the exact active Okta console process/arguments, stopped that UI process, and restarted the console explicitly in personal mode on 127.0.0.1:4180. No sandbox VM, workspace, resident service, provider setting or authentication policy was changed. Updated canonical authentication/runbook status and the roadmap's active priorities: owner-bound browser terminal, workspace lifecycle, remaining policy acceptance, then performance/soak evidence.
- **Validation:** Real loopback bootstrap, expected local-pilot/operator identity with organization_sso false, session listing (13 historical records, zero ready sessions) and resident cleanup active/non-stale checks passed. [Evidence](results/oidc-console-20261114/personal-mode-restored.json). The first evidence-file write used the parent working directory and failed after successful HTTP checks; saved the observed sanitized result at the correct repository path afterward. Git whitespace check passed.
- **State / next:** Personal console running; OIDC candidate retained; no real SSO claim, no new feature or model task tested. Changes uncommitted/unpushed. Next implement and validate the local browser terminal without weakening existing container/owner/network policy; organization SSO remains deferred before remote or untrusted multi-user deployment.


## 2026-11-14T16:35:17+05:30 — Bind assigned user and prepare private Okta console launch

- **Changed:** Confirmed app assignment and read exact user ID from user-supplied profile screenshots. Updated only the external temporary public configuration with an explicit member assignment, no operator promotion. Prepared /private/tmp/sandbox-console-okta/start.command (0700) using hidden raw Terminal input, tracing disabled and exec into the optional-dependency interpreter. No secret is stored in a file or command argument. Configuration remains 0600 outside Git.
- **Validation / transition:** Offline profile shape and zsh launcher syntax passed. Verified the exact existing personal console PID/command on callback port 4180 before terminating that process; the port was available afterward. No VM, worker resource or resident service was modified. [Sanitized readiness evidence](results/oidc-console-20261114/private-launch-preparation.json).
- **Failures / limits:** The initial sandboxed process-inspection command was denied; escalated read-only inspection succeeded. No client secret supplied or real login tested. Screenshot-derived user ID is configured, but final signed provider subject must still match during actual sign-in. Temporary files/environment may need recreation after OS cleanup.
- **State / next:** Prior personal UI stopped for the user to launch Okta mode on its registered port. Changes uncommitted/unpushed. User enters the secret privately in Terminal and completes browser sign-in; then verify authenticated member identity, bootstrap protection and logout behavior.


## 2026-11-14T16:27:08+05:30 — Verify real tenant public discovery and prepare private configuration draft

- **Changed / verified:** Read only public organization and default-server OIDC discovery endpoints using certificate-verified HTTPS, without secrets, authorization codes or token requests. Both returned compatible code/S256/RS256/client-secret-basic metadata and same-origin HTTPS endpoints. Selected the organization issuer for OIDC SSO only, consistent with the provider documentation; no application API access-token validation is introduced. Prepared a permission-restricted configuration draft outside Git at /private/tmp/sandbox-console-okta/okta.json using the provided public client ID; exact assigned subject remains a placeholder. Offline shape preflight passed. [Sanitized evidence](results/oidc-console-20261114/public-discovery.json).
- **Failures / limits:** Web browsing could not access the tenant-specific discovery URLs; direct HTTPS retrieval succeeded. Public metadata does not verify the client ID, secret, callback registration, app assignment or successful login. Latest user profile screenshot omits the sandbox app from assigned applications. No secret supplied, worker resource changed, console restarted or real login attempted.
- **State / next:** Draft is temporary and not production-ready; repository changes uncommitted/unpushed. Next assign the app to the user, obtain the exact subject/user ID from the profile URL, update the explicit member assignment, and have the user enter the client secret privately before testing actual login.


## 2026-11-14T15:03:31+05:30 — Optional Okta OIDC login and per-browser request identity candidate

- **Changed:** Implemented optional Authlib code/S256-PKCE exchange, joserfc RS256 verification with Authlib OIDC claims, exact provider discovery and same-origin HTTPS endpoints, bounded responses/timeouts and no ambient proxy/netrc credentials. Added browser-bound one-use transactions, independent opaque/CSRF-protected server sessions, rotation/logout, idle/absolute/token expiry, assignment/role reload and immutable per-request worker adapter bindings. Personal mode remains default; Okta bootstrap cannot create personal operator authority. Added login page/sign-out/identity labels and disabled privileged terminal export in Okta mode pending secure relay. Canonical auth/runbook/spec/requirements/overview docs updated.
- **Validation:** Twenty signed-synthetic-token/provider/real-loopback HTTP tests passed, including actual Authlib token-request construction, negative algorithms/signature/issuer/audience/nonce/time/hash cases, discovery/transport failures, browser binding/replay, local logout/expiry/revocation/demotion, concurrent browser identities and real worker command immutability. Twelve config/profile tests passed in both standard-library and optional-dependency environments, six ownership regressions and 18 existing console API tests passed; one separate live VM lifecycle test skipped. JS syntax, Python AST, DOM selector IDs, new documentation links, dependency consistency and Git whitespace checked. [Evidence](results/oidc-console-20261114/).
- **Corrections / failures:** Initial OIDC suite exposed two synthetic fixture errors (duplicate nonce argument and response streaming fixture state); both corrected. A negative hash test then showed that a present access-token hash was skipped without an access token; candidate now rejects missing/empty access tokens when that hash is present, and verifies mismatches through the library. Moved off deprecated authlib.jose onto joserfc before final passing run. No protection was relaxed.
- **Browser / cleanup:** Reviewed the actual sign-in page content in the in-app browser against an isolated synthetic-provider loopback server. Preview stopped afterward. No real provider login, private credential, model call, real worker resource mutation or pilot service restart occurred. Signing keys stayed in memory. Optional dependencies installed only into /private/tmp/sandbox-oidc-venv; repository venv path is ignored.
- **Limits / state:** Candidate implemented but real Okta tenant/app login remains unverified; user confirmed no tenant yet. OIDC HTTP tests use a recording worker adapter; earlier real worker ownership evidence used simulated principals. Local assignment revocation is covered; upstream continuous/back-channel revocation, remote HTTPS, centralized auth audit and secure attach relay remain open. Existing pilot stays personal mode. Changes uncommitted/unpushed.
- **Next:** Register/configure an Okta web application and assigned subjects, supply the client secret privately server-side, then verify actual login and distinct-user worker isolation before organization rollout.


## 2026-11-14T11:12:01+05:30 — Personal mode and optional Okta authentication preparation

- **Changed:** Added explicit personal/Okta CLI profiles, bounded strict public-config validation, offline preflight without Lima/network/socket startup, and a fail-closed Okta startup gate. Added deterministic exact issuer/subject owner mapping and explicit assigned-member/operator role mapping; these helpers do not validate tokens and are not wired into requests. Default personal principal/role/storage behavior remains intact. Added placeholder-only configuration and canonical authentication design, planned flow and setup/acceptance gates; linked console, ownership, requirements, control-plane and documentation index.
- **Validation:** Twelve new profile/CLI tests, six ownership regressions and 18 local HTTP/API regressions passed; one separate live worker lifecycle test skipped. Checked missing/ambiguous/oversized settings, callback matching, assignment denial, role restrictions, cross-issuer mappings, diagnostics sanitization, no local fallback and gating before adapter/socket creation. Actual CLI preflights succeeded with explicit pending-SSO metadata. Python AST and new document links checked. [Evidence](results/auth-profiles-20261114/).
- **Failed / remaining:** No observed test failures. User confirmed no Okta tenant/application yet. This is integration preparation, not implemented SSO: OIDC redirect/code exchange/signature verification and server browser sessions are still pending. No tenant, provider login, distinct authenticated users, credentials, model call or remote exposure tested. No existing console/VM service restarted or migrated by this batch.
- **State / next:** Changes uncommitted/unpushed. Next implement a maintained-library OIDC adapter and per-request session identity, then register an Okta application and run real distinct-user/failure tests. Remote HTTPS and secure attach remain separate deployment gates.


## 2026-11-14T01:36:47+05:30 — Owner-scoped sessions, per-user volumes and role foundation

- **Changed:** Added bounded trusted principal/member/operator bindings, additive session-owner migration, owner-scoped idempotency, separate hashed-owner workspace volumes/resource labels, member quota two within global five, ownership checks for CRUD/reconcile/history/alerts/audit/monitoring and owner-only credential attach. Denied accesses are recorded privately; clients cannot supply owner/role through headers/body. Identity metadata/UI explicitly says SSO is disconnected. Default local-pilot storage/deadlines/operator behavior preserved.
- **Validation:** Six ownership unit tests, seven journal tests, eight rule tests, four sanitization tests and 18 local API tests passed (one separate live lifecycle test skipped). A disposable shared VM state with two member APIs and an operator API passed 19 real HTTP/storage/cleanup checks. Original worker suite passed 22 regression checks. Verified workspace separation, same-owner persistence, fresh homes, foreign target/action denial, scoped evidence and operator expiry/stop across owners. [Evidence](results/user-isolation-20261114/).
- **Migration / checks:** Created a private metadata backup before migrating the real pilot. All 13 prior session owners remained local-pilot, legacy volume names and quota remained unchanged, and monitoring/alerts/resident health passed. Explicit unassigned principal CLI listing returned no legacy sessions. Browser verified local identity/quota/SSO-not-connected display with zero console errors. Syntax/whitespace checks passed. Preview /private/tmp/sandbox-console-identity.png.
- **Corrections / limits:** Tightened CLI defaults so an explicitly selected principal defaults to member; aligned alert-action response actor with its recorded principal. A missing-session cleanup now denies before resource access, so the foreign-resource regression accepts that stricter rejection while checking preservation. No observed runtime failures or protection relaxations. These are simulated/trusted principals, not real organization authentication; local OS/Docker operator remains trusted and editable terminal handoff is not suitable for untrusted users. SSO provider/configuration question remains pending. No new model calls, device logins, credentials or cross-kernel exploit tests.
- **State / next:** Isolated test resources/state/volumes removed. Original pilot and resident service running. Docs updated; changes uncommitted/unpushed. Next connect verified SSO subjects/roles to the ownership boundary, replace privileged terminal handoff for real users and run authenticated distinct-user acceptance tests.


## 2026-11-14T00:19:37+05:30 — Versioned detection thresholds and review guidance

- **Changed:** Added `pilot-review-v1` catalog, observed-denial burst threshold, persisted sustained resource/incomplete-sample streaks, worker-wide collection-gap/clock-change signal, rule-version metadata and read-only catalog API. Resident collection now samples agent Docker resources. UI adds seven rule cards, current review guidance, worker scope labels and expanded history filters. New evidence versions are stored; existing rows keep an explicit legacy label. Installer/test dependency copies updated and worker deployed.
- **Validation:** Eight rule tests, seven journal tests, four sanitization/policy tests and 17 API tests passed; one separate live lifecycle test skipped. Isolated service passed 11 checks. A disposable session made five rejected CONNECT requests; resident collection created a high-priority burst with five unique denial events and no duplicates on the next collection. Eight live burst/cleanup checks passed. Browser verified seven rules, guidance, history filter and resolution of only validation alerts; zero console errors. [Evidence](results/alert-rules-20261114/), [criteria](docs/security/ALERT_REVIEW_RULES.md).
- **Corrections / limits:** Updated the retention regression assertion to allow the intentionally new collector-gap signal when test time jumps 31 days. No production test failure or weakened protection. Sustained resource/gap cases used injected samples, not host stress or actual sleep tests. Counts use observation time/flow-stage dedup and can reflect backfilled traffic; alerts are not attack attribution. No auto-stop, UI rule editing, external notification, credentials or raw traffic/body capture.
- **State / next:** Disposable session stopped; workspace retained and two test alerts resolved. Local console and resident service running. Preview /private/tmp/sandbox-console-detection-rules.png. Docs updated; changes uncommitted/unpushed. Next calibrate rules against representative allowed workloads and controlled negative tests, then extend reviewed signal/delivery coverage.


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

# Managed workspace quotas: opt-in integration

**Status (2026-11-16):** The root-owned storage service and managed-worker integration are implemented and deployed for explicitly enrolled owners. A new-owner canary passed **22 live checks**, including aggregate limits across two sessions, cross-owner denial, mount/limit validation, export, expiry, recovery and backing-data deletion. **The actual `local-pilot` workspace is now migrated and enrolled with an enforced 5 GiB limit; its original volume is retained for rollback.** See the [migration/recovery runbook](../runbooks/WORKSPACE_MIGRATION.md). Root filesystem features, fstab and sudoers were not changed. The mount-recovery service is installed and enabled; a complete VM reboot has not been tested.

## Initial candidate evidence

The current Lima VM has an ext4 root filesystem without quota/project features enabled. Docker uses `/var/lib/docker`. Offline root-filesystem changes are not needed for this experiment. The candidate uses a separate 6 GiB sparse XFS image with `prjquota`, `nosuid` and `nodev`, and project-inheriting workspace directories. The implemented pilot backend uses one root-owned, fully preallocated 6 GiB XFS image per enrolled owner, with a 5 GiB project limit. A shared managed disk/pool remains a possible later optimization.

[XFS project quotas](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/8/html/managing_file_systems/assembly_limiting-storage-space-usage-on-xfs-with-quotas) bound directory trees independently of the sandbox UID. Docker's [local-volume mount options](https://docs.docker.com/engine/storage/volumes/) support attaching the mounted project directory; this is not a volume-name or container-memory limit. Our candidate test uses UID 10001, the immutable agent image, pinned runsc, a read-only container root, no network, dropped capabilities and no new privileges.

[Live evidence](../../results/workspace-quota-20261115/live.json) records **16/16 passing checks**:

- Project accounting/enforcement is enabled and the actual hard block limit reads back as 5,242,880 KiB (5,368,709,120 bytes).
- An unprivileged gVisor process writes normally; multiple files, including a nested directory, allocate just under 5 GiB in total. Host block counts confirm allocation rather than sparse apparent size.
- Allocation above the limit fails while the filesystem still has more than 512 MiB free. Actual writes at the boundary fail with `ENOSPC`, with a measured 7 MiB partial write before denial in this run.
- A host process dropped to UID/GID 10001 also receives errno 28. This agrees with XFS project-quota behavior: the [kernel quota definitions](https://kernel.googlesource.com/pub/scm/linux/kernel/git/dgc/xfsprogs-dev/+/refs/heads/master/libxfs/xfs_quota_defs.h) explicitly support `ENOSPC` for project quotas. It is not evidence that gVisor changed `EDQUOT`.
- A second project with the same UID still allocates data, and its separate 32 MiB limit is enforced.
- Removing allocated files allows writes again. Content, numeric hard limit and write enforcement survive an unmount/remount and fresh containers.
- Disposable containers, Docker volumes, mount, loop device, image and directory are cleaned up. An independent inventory found zero test leftovers.

The cap concerns allocated filesystem blocks, including charged metadata; it is not a guarantee of exactly 5 GiB of application payload. Sparse apparent sizes, inode limits and physical pool capacity are different measurements. A 100,000-inode limit was configured but inode-exhaustion acceptance is still pending. The experiment uses preallocation plus writes near the boundary, not a sustained 5 GiB throughput benchmark. Manual remount is not VM-reboot or recovery acceptance.

[36 workspace regression tests](../../results/workspace-quota-20261115/regressions.json) passed. Seven new cases cover opt-in/root/host/tool/free-space guards and missing, malformed or ambiguous quota readback. HTTP, terminal and model tests were not repeated because this batch changes no service/session behavior.

## Reproduce the isolated test

Read [the test script](../../scripts/test_workspace_quota_live.py) before running it. It only accepts an explicit opt-in as root on `lima-gvisor-poc`; it requires the existing pinned image/runtime, XFS tools and at least 9 GiB of free space. Run one experiment at a time. The script creates only randomly named `poc-quota-test-*` resources and `/var/tmp/gvisor-quota-test-*` storage; it imports no worker state and reads no user workspace or credential files.

```sh
limactl copy scripts/test_workspace_quota_live.py gvisor-poc:/tmp/gvisor-workspace-stage/
limactl shell gvisor-poc -- sudo -n python3 /tmp/gvisor-workspace-stage/test_workspace_quota_live.py --allow-disposable-storage-test
```

Every Docker/container command is bounded. Normal failures and SIGTERM attempt cleanup; cleanup checks the exact mount source, loop backing file and test labels before removal, and reports errors instead of forcing foreign/busy resources. Hard kill or VM crash can leave storage behind: inspect mount/loop/label ownership before manual recovery. This standalone candidate script is not the managed recovery service described below.

Initial failures are preserved: [first attempt](../../results/workspace-quota-20261115/initial-live-failure.json), [diagnostics](../../results/workspace-quota-20261115/diagnostic.json), [host-errno diagnosis](../../results/workspace-quota-20261115/host-errno-diagnostic.json). The quota command suppresses zero-usage rows without `-v` and reports filesystem rows, not project-ID rows. Shell child launches at 128 MiB produced intermittent ENOMEM; direct processes fixed that. A strict EDQUOT assertion was incorrect for XFS project quotas; numeric readback, remaining capacity, independent-project writes and the host errno check distinguish quota exhaustion from a full filesystem.

## Managed integration and deployment

The root executable [workspace_quota_service.py](../../scripts/workspace_quota_service.py) is installed as `/usr/local/libexec/gvisor-workspace-quota`. Root-owned manifests/images live under `/var/lib/gvisor-workspace-quota`; registered worker namespaces and trusted VM UIDs live in `/etc/gvisor-workspace-quota/workers.json`. Those directories are private to root. The helper derives all backing paths and volume names; it does not accept a caller-selected mount/image path. It serializes operations with a root-owned lock, validates caller UID against registration, and exposes only fixed operations. The trusted VM worker already has administrative Docker/sudo access; this is not an organization-authentication boundary or a new tenant-facing root API.

[install_workspace_quota.sh](../../scripts/install_workspace_quota.sh) installs/verifies the helper and [systemd unit](../../deploy/systemd/gvisor-workspace-quota.service), registers an already-initialized worker state directory, and enables mount recovery after Docker/local filesystems. It does not enroll owners or migrate files. Run it inside the VM from a reviewed source checkout:

```sh
bash scripts/install_workspace_quota.sh "$HOME/.local/state/gvisor-poc-worker"
```

Owner enrollment is an explicit trusted-operator configuration in the worker state directory: `quota-owners.json`, owned by the VM worker UID with mode 0600 and schema `{"owners":["new-owner-id"]}` for new owners; the migration CLI also maintains a `migrated` owner list to select the verified replacement volume. There is no browser enrollment endpoint. Unknown/malformed/publicly readable/symlink configurations are rejected; a dangling symlink cannot fall back to ordinary storage. **Do not enroll an existing owner before a migration/cutover is prepared:** an existing ordinary volume returns `quota_migration_required` and is never reformatted.

The worker adapter [workspace_quota.py](../../scripts/workspace_quota.py) binds every helper request to the worker namespace and authenticated principal. Create allocates/reserves 6 GiB of guest filesystem capacity, retains at least 4 GiB guest headroom, formats only the newly created image, assigns project inheritance and a 5 GiB hard limit, then creates the registered local-driver volume. Capacity is checked under the global storage lock. Formatting uses `mkfs.xfs -K` to preserve allocation. Live validation also checks the image's allocated blocks and refuses a lost reservation. A separate 512 MiB formatting check confirmed both default/keep modes retained allocation on this VM. This reserves space in the guest filesystem, not a physical-capacity guarantee on the Mac's thin-provisioned VM storage.

Create, attach, storage inspection, export and deletion require a matching root-owned manifest, volume name/options/labels, filesystem UUID, actual XFS mount, enabled accounting/enforcement, numeric 5 GiB limit, workspace UID/GID and project inheritance. Ordinary/unregistered bind-backed volumes remain rejected. Status never silently mounts or repairs storage; Create and the boot service may restore a known ready filesystem and must revalidate it before use. Missing mounts, changed limits and unavailable helpers fail closed; there is no fallback to an ordinary Docker volume for enrolled owners.

Quota accounting is reported separately from the sandbox user's readable-file `du` sample. The API exposes `hard_quota_enforced`, `quota_bytes`, `quota_used_bytes` and `quota_remaining_bytes`; it does not expose manifest identities or host paths. The UI shows the verified hard limit/remaining blocks for enrolled workspaces and keeps legacy storage explicitly advisory. Failed samples clear the displayed quota status.

Export retains its 16 MiB/10,000-entry conservative archive limits and read-only probe. Owner-confirmed deletion consumes its existing one-use consent and commits the worker audit before calling the backend with the expected storage identity. The backend checks all container references, marks the manifest `deleting`, removes volume metadata, unmounts/detaches its own filesystem and deletes its backing image/manifest/directory. Success requires verified backend absence, not merely missing Docker metadata. A replacement filesystem gets a fresh identity, so old storage identities cannot delete it.

An interrupted allocation is left explicitly incomplete for operator review. An interrupted deletion cannot be recreated by Create or boot restore; it can only be completed against its original storage identity. The root `delete` operation supports resuming its own `deleting` state when the remaining mount/image metadata permits it. Ambiguous leftovers require operator inspection; the service never force-removes busy/foreign resources. Worker audit may remain `requested` or become `unknown` after interruption. Boot restore skips incomplete manifests rather than presenting their data as ready. `systemctl is-active` alone does not establish that a particular workspace is valid; every data-plane operation checks that workspace again.

## Managed validation and remaining gates

[Managed canary evidence](../../results/workspace-quota-integration-20261115/live.json) records **22/22 passing checks**. Four observed creates took 0.947, 0.835, 0.786, 0.815 seconds in this run; these are a small canary sample, not p95 or terminal/authenticated readiness. The test made **zero model requests** and used disposable data/simulated principals only.

- Two managed sessions reached login-ready on the same quota volume and shared a synthetic file; allocation across both sessions hit the aggregate 5 GiB boundary.
- Another principal could neither see nor delete the first owner's backend. A temporarily changed 6 GiB limit and a missing mount were rejected; the test restored the 5 GiB setting immediately.
- Active export/deletion were blocked. After stop, read-only export matched the synthetic fixture. Freeing allocated files recovered writes.
- Restarting the storage service restored a manually unmounted filesystem; a fresh session retained data and verified quota settings. Injecting a past expiry removed agent/gateway containers while retaining the quota workspace.
- Confirmed deletion removed the actual backing store and recorded the audit. Recreating storage produced an empty workspace/new identity; the old identity could not delete it.
- All canary stores, loops, volumes, registrations and state were removed. At that initial test date, the root service remained enabled/active with only the legacy worker namespace registered and no owner enrolled there. The November 16 migration below supersedes that enrollment state.

[106 regression tests passed; one opt-in live lifecycle test was skipped](../../results/workspace-quota-integration-20261115/regressions.json). Twenty-five new adapter/service cases include malformed or untrusted metadata, ownership, capacity, no-fallback behavior, changed mount/UUID/enforcement/limits, deletion ordering and backing-data failure. Initial new tests found the dangling-symlink fallback and malformed/negative quota-response gaps; these were corrected and rerun. Static compile/syntax/diff checks passed. Installing the unit emitted existing system XFS scrub `CPUAccounting` deprecation warnings; the unit verification succeeded.

A temporary browser console displayed the verified 5 GiB hard limit and remaining space, refreshed successfully and had no console errors. Its disposable quota store and console were removed. [Legacy pilot evidence](../../results/workspace-quota-integration-20261115/legacy-pilot.json) records the advisory state before migration; it is historical, superseded by the November 16 cutover. No credential files or user workspace contents were read by the quota tests.

| Gate | Current state |
|---|---|
| Candidate 5 GiB allocation/write boundary, recovery and remount | Passed on disposable storage |
| Root-owned provisioning, capacity reservation and boot-service installation | Implemented; canary passed. Inode exhaustion and full crash recovery remain untested |
| Worker validation before create/attach/usage/export/deletion | Implemented; unit and missing-mount/changed-limit canary checks passed |
| Quota-aware export and confirmed backing-data deletion | Implemented and canary-validated |
| Same-owner concurrent sessions, cross-owner denial, stop/expiry and service recovery | Passed with simulated local principals; full VM reboot and real organization identities remain untested |
| Existing-user migration/rollback | Implemented; 16-check disposable canary passed. Actual pilot cutover verified, original retained; finalization awaits acceptance |
| Five-session p95, full reboot, sustained uptime/soak and larger exports | Pending |

## Existing-user migration (2026-11-16)

The [operator migration workflow](../runbooks/WORKSPACE_MIGRATION.md) now implements verified prepare/copy/cutover, guarded rollback, interrupted-copy abort and explicit finalization. The actual pilot's 11 entries / 3,765 bytes matched before and after copying; a managed session accessed the quota workspace successfully and was stopped. Hard limit reads back as 5,368,709,120 bytes, with zero active sessions. Its original volume remains retained and permanent deletion is guarded until migration recovery data is resolved.

[Migration canary](../../results/workspace-migration-20261116/live.json): 16 checks passed, including changed-data rollback refusal and interrupted-copy abort. [Existing quota regression](../../results/workspace-migration-20261116/existing-quota-regression.json): 22 checks passed. [Affected regressions](../../results/workspace-migration-20261116/regressions.json): 123 passed / one skipped. UI hard-limit display and retained-backup deletion guard were verified without browser console errors. Full reboot, crash recovery and five-session performance/soak remain open.

The 38 GiB VM had roughly 22 GiB free during inspection. Five sessions sharing one user's 5 GiB workspace differs from five users each entitled to 5 GiB. Provisioned pool capacity, metadata, journal, rollback storage and host headroom must be budgeted before guaranteeing multi-user capacity; sparse images alone do not reserve it.

The UI distinguishes enrolled quota-backed storage, including the migrated pilot, from any remaining advisory legacy storage; production/organization readiness claims remain gated by the work above. See [current requirements](../REQUIREMENTS_STATUS.md), [local console](../runbooks/LOCAL_CONSOLE.md) and [roadmap](PLATFORM_ROADMAP.md).

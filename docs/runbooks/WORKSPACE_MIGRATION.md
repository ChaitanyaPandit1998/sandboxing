# Existing workspace migration and recovery

**Status (2026-11-16):** The actual `local-pilot` workspace is migrated to the enforced **5 GiB** backend. All 11 entries / 3,765 bytes of file content matched after copying. A temporary managed session reached ready and verified workspace access, then was stopped. The original ordinary volume is retained; no rollback copy has been deleted. The UI verifies hard quota and blocks permanent workspace deletion while this copy remains.

[Actual cutover evidence](../../results/workspace-migration-20261116/pilot-cutover.json), [16-check disposable migration canary](../../results/workspace-migration-20261116/live.json), [22-check existing quota regression](../../results/workspace-migration-20261116/existing-quota-regression.json), [123 passing tests / one skipped](../../results/workspace-migration-20261116/regressions.json).

## Operator workflow

Run from Mac Terminal against the existing VM. This CLI is a trusted operator facility, not a tenant-facing HTTP endpoint. Stop all owner sessions first; running and stopped containers referencing either copy also prevent root storage operations. The worker lock serializes managed operations for the maintenance window.

```sh
limactl shell gvisor-poc -- bash -lc 'python3 "$HOME/gvisor-managed-pilot/scripts/workspace_migration.py" status'
```

The private status record supplies the migration `id` and phase. Keep it in the VM; do not publish raw records or edit enrollment flags manually. `local-pilot` is already **active**: do not prepare a second migration. For another eligible legacy workspace, `prepare --principal OWNER` inventories, copies and verifies it while retaining its original binding. Replace `OWNER` and `MIGRATION_ID` with the reviewed owner/job values and pass the same `--principal OWNER` to every command when operating on a non-default owner.

```sh
# Prepare only for a legacy owner that has not already been migrated.
limactl shell gvisor-poc -- bash -lc 'python3 "$HOME/gvisor-managed-pilot/scripts/workspace_migration.py" prepare --principal OWNER'
# Cut over an already prepared local-pilot migration.
limactl shell gvisor-poc -- bash -lc 'python3 "$HOME/gvisor-managed-pilot/scripts/workspace_migration.py" cutover --migration-id MIGRATION_ID --confirm "MIGRATE WORKSPACE"'
```

Cutover atomically enrolls the owner and selects the verified `-quota` volume. Worker volume lookup is dynamic, including already-running reconciler processes. The original volume remains untouched. A failed validation restores the previous enrollment configuration; inspect status before retrying.

## Rollback and staged-copy removal

Rollback requires both copies to still match the verified snapshot. It switches back to the original volume and retains the staged quota copy. If either copy has changed, rollback fails closed rather than dropping newer work; stop and arrange a separately reviewed recovery/merge.

```sh
limactl shell gvisor-poc -- bash -lc 'python3 "$HOME/gvisor-managed-pilot/scripts/workspace_migration.py" rollback --migration-id MIGRATION_ID --confirm "ROLLBACK WORKSPACE"'
# Only after rollback, or before cutover; permanently removes the staged duplicate.
limactl shell gvisor-poc -- bash -lc 'python3 "$HOME/gvisor-managed-pilot/scripts/workspace_migration.py" discard --migration-id MIGRATION_ID --confirm "DISCARD STAGED COPY"'
# For an interrupted prepare in phase copying; preserves the unchanged original.
limactl shell gvisor-poc -- bash -lc 'python3 "$HOME/gvisor-managed-pilot/scripts/workspace_migration.py" abort --migration-id MIGRATION_ID --confirm "ABORT STAGED COPY"'
```

An aborted preflight with no allocated target can also be cleared with `abort`. Unexpected identities, modified originals, foreign/busy resources or ambiguous leftovers require operator inspection; never force-delete or rename volumes to bypass these checks.

## Accepting the new backend

Use the migrated workspace before accepting it. **Finalization permanently deletes the original rollback copy.** This was tested only on disposable fixtures; it has not been run for the real pilot. Stop all consumers, review status and confirm the active quota backend before executing:

```sh
limactl shell gvisor-poc -- bash -lc 'python3 "$HOME/gvisor-managed-pilot/scripts/workspace_migration.py" finalize --migration-id MIGRATION_ID --confirm "DELETE ROLLBACK COPY"'
```

Finalization checks the original identity and snapshot, preserves newer work on the active quota backend, and records an intermediate `finalizing` state for retries. Once finalized, ordinary owner-confirmed workspace deletion is available again. Until then, the UI reports that a rollback copy is retained; it does not imply all stored copies can be erased through the ordinary deletion action.

## Copy policy and limits

The root helper accepts only the registered ordinary source and derived target; callers cannot supply arbitrary paths. It preflights at most **90,000 entries** and **5 GiB minus 32 MiB** of unique regular-file logical content. Available capacity must also cover a fully allocated 6 GiB backing image and guest headroom. Sparse files are copied densely and may fail allocation safely.

The copier preserves regular files, directories, hard links, symbolic links, numeric ownership, modes and nanosecond modification times. It never follows symlinks, rejects cross-filesystem entries, special files and xattrs/ACLs, and requires source-root UID/GID 10001. Content hashes, link topology and metadata are checked before and after copying. Unsupported or changing data prevents cutover. Aggregate evidence contains counts and match results, not filenames, content or temporary login homes. Reading workspace files is necessary to verify their contents; this is not a claim that arbitrary workspace files cannot contain secrets.

The original retained copy is recovery data, not an ongoing backup or merge service. Host administrators can mutate data outside the worker lock. Full VM reboot/crash recovery, large-dataset migration, inode exhaustion and sustained multi-session performance remain unverified. See [quota backend details](../platform/WORKSPACE_QUOTAS.md).

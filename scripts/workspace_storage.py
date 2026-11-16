"""Owner-only workspace metadata; never return file names or host mount paths."""
import hashlib
import re
import time
import uuid

WORKSPACE_BUDGET_BYTES = 5 * 1024**3

# du runs directly as PID 1: no shell or child-process launcher is needed.
# The worker Docker call has a 30-second timeout and finally removes the probe.


def describe(worker):
    """Caller holds worker.locked(); identity always comes from the worker."""
    from manage_codex_session import AGENT, RUNTIME, WorkerError
    rows = worker.db.execute('SELECT state FROM sessions WHERE owner=?', (worker.principal,)).fetchall()
    data = {'owner': worker.principal, 'state': 'not_created',
            'active_sessions': sum(row['state'] in ('ready', 'provisioning', 'stopping') for row in rows),
            'retention': 'until_explicit_deletion', 'hard_quota_enforced': False,
            'budget_bytes': WORKSPACE_BUDGET_BYTES, 'over_budget': None,
            'quota_bytes': None, 'allocated_bytes': None, 'measurement_status': 'not_measured',
            'sampled_at': time.time(), 'measurement_scope': 'allocated bytes readable by the sandbox user; live, non-atomic sample'}
    data['deletion_history'] = [dict(row) for row in worker.db.execute(
        "SELECT id,outcome,at FROM authorization_audit WHERE actor=? AND action='delete_workspace' ORDER BY id DESC LIMIT 10", (worker.principal,))]
    volume = checked_volume(worker)
    if volume is None:
        return data
    quota = volume.get('_quota')
    if quota:
        data.update(hard_quota_enforced=True, quota_bytes=quota['quota_bytes'],
                    quota_used_bytes=quota['quota_used_bytes'], quota_remaining_bytes=quota['quota_remaining_bytes'])
    name = 'poc-workspace-usage-' + uuid.uuid4().hex
    try:
        output = worker.docker('run', '--name', name, '--pull=never',
            '--label', worker.label, '--label', 'poc.purpose=workspace-usage',
            '--label', 'poc.owner='+hashlib.sha256(worker.principal.encode()).hexdigest(),
            '--runtime='+RUNTIME, '--network=none', '--read-only', '--user=10001:10001',
            '--cpus=1', '--memory=128m', '--pids-limit=32', '--cap-drop=ALL',
            '--security-opt=no-new-privileges', '--mount',
            'type=volume,source='+worker.volume+',target=/workspace,readonly',
            '--entrypoint=du', AGENT, '-sk', '/workspace')
    except WorkerError:
        output = ''  # Permission, runtime, and timeout failures are unknown usage.
    finally:
        try:
            worker.docker('rm', '-f', name)
        except WorkerError:
            if worker.exists('container', name) is not None:
                raise WorkerError('workspace_probe_cleanup_failed') from None
    data['state'] = 'retained'
    data['measurement_status'] = 'incomplete'
    match = re.fullmatch(r'([0-9]+)\s+/workspace', output.strip())
    if match and len(match[1]) <= 16:
        value = int(match[1]) * 1024
        if value <= 2**53-1:
            data.update(allocated_bytes=value, measurement_status='measured', over_budget=value > WORKSPACE_BUDGET_BYTES)
    data['sampled_at'] = time.time()
    return data


def checked_volume(worker):
    from manage_codex_session import WorkerError
    volume = worker.exists('volume', worker.volume)
    from workspace_quota import enabled, validate
    if volume is None:
        if enabled(worker):
            validate(worker, None)
        return None
    worker.ensure_owned(volume)
    owner_label = (volume.get('Labels') or {}).get('poc.owner')
    if owner_label is not None and owner_label != hashlib.sha256(worker.principal.encode()).hexdigest():
        raise WorkerError('resource_ownership_mismatch')
    if enabled(worker):
        volume['_quota'] = validate(worker, volume)
        return volume
    if volume.get('Name') != worker.volume or volume.get('Driver') != 'local' or volume.get('Options'):
        raise WorkerError('workspace_storage_unsupported')
    return volume

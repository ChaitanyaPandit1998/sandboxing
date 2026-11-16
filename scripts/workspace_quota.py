"""Trusted worker binding to the root-owned optional quota backend."""
import json
import os
import re
import stat
import subprocess
from manage_codex_session import WorkerError

HELPER = '/usr/local/libexec/gvisor-workspace-quota'
LIMIT = 5 * 1024**3


def configuration(worker):
    path = worker.root/'quota-owners.json'
    if not os.path.lexists(path):
        return {'owners': [], 'migrated': []}
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077 or info.st_size > 8192:
            raise ValueError()
        config = json.loads(path.read_text())
        if not isinstance(config,dict) or set(config)-{'owners','migrated'} or 'owners' not in config:
            raise ValueError()
        config.setdefault('migrated',[])
        for values in config.values():
            if not isinstance(values,list) or len(values)>128 or any(not isinstance(owner,str) or not re.fullmatch('[a-z0-9][a-z0-9._-]{0,63}',owner) for owner in values):
                raise ValueError()
        if not set(config['migrated']).issubset(config['owners']):
            raise ValueError()
        return config
    except (OSError,ValueError,KeyError,TypeError):
        raise WorkerError('quota_config_invalid') from None


def enabled(worker):
    return worker.principal in configuration(worker)['owners']


def volume_name(worker,owner,canonical):
    return canonical+'-quota' if owner in configuration(worker)['migrated'] else canonical


def call(worker, action, identity=None):
    if action not in ('status', 'create', 'delete', 'prepare-migration', 'migration-state', 'abort-migration', 'finalize-migration', 'create-migrated'):
        raise WorkerError('quota_action_invalid')
    command = ['sudo', '-n', HELPER, action, worker.namespace, worker.principal]
    if identity is not None:
        command += ['--identity', identity]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=600 if action=='prepare-migration' else 90)
        if result.returncode:
            code = json.loads(result.stderr)['error']
            raise WorkerError(code if re.fullmatch(r'(?:quota|migration)_[a-z_]+|workspace_in_use', code) else 'quota_storage_unavailable')
        data = json.loads(result.stdout)
        if not isinstance(data, dict):
            raise ValueError()
        return data
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        raise WorkerError('quota_storage_unavailable') from None


def validate(worker, volume, snapshot=None):
    data = snapshot if snapshot is not None else call(worker, 'status')
    if not isinstance(data, dict):
        raise WorkerError('quota_volume_mismatch')
    if data.get('state') == 'absent' and volume is None:
        return None
    if (volume is None or volume.get('Name') != worker.volume or data.get('state') != 'ready' or data.get('volume') != worker.volume
            or data.get('hard_quota_enforced') is not True or data.get('quota_bytes') != LIMIT
            or any(type(data.get(key)) is not int or data[key] < 0 for key in ('quota_used_bytes', 'quota_remaining_bytes'))
            or data.get('quota_remaining_bytes') != max(0, LIMIT-data.get('quota_used_bytes', 0))
            or not isinstance(data.get('identity'), str)
            or data.get('backend') != 'xfs-project-v1' or not re.fullmatch('[a-f0-9]{32}', data.get('identity', ''))
            or volume.get('Driver') != 'local' or volume.get('Options') != data.get('options')
            or (volume.get('Labels') or {}).get('poc.storage-id') != data['identity']
            or (volume.get('Labels') or {}).get('poc.storage') != 'xfs-project-v1'):
        raise WorkerError('quota_volume_mismatch')
    return data


def ensure(worker):
    action='create-migrated' if worker.principal in configuration(worker)['migrated'] else 'create'
    snapshot = call(worker, action)
    volume = worker.exists('volume', worker.volume)
    worker.ensure_owned(volume)
    validate(worker, volume, snapshot)


def remove(worker, identity):
    if call(worker, 'delete', identity).get('deleted') is not True:
        raise WorkerError('quota_deletion_unverified')
    if call(worker, 'status').get('state') != 'absent':
        raise WorkerError('quota_deletion_unverified')

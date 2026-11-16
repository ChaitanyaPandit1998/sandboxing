#!/usr/bin/python3
"""Root-owned gvisor workspace storage service; fixed paths, no caller-selected mounts."""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import subprocess
import sys
import time

BASE = Path('/var/lib/gvisor-workspace-quota')
CONFIG = Path('/etc/gvisor-workspace-quota/workers.json')
QUOTA = 5 * 1024**3
IMAGE_BYTES = 6 * 1024**3
RESERVE = 4 * 1024**3
BACKEND = 'xfs-project-v1'


class StorageError(Exception):
    pass


def run(*args, absent=False, timeout=30):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        if absent and result.returncode == 1:
            return None
        raise StorageError('quota_storage_command_failed')
    return result.stdout.strip()


def trusted(path, directory=False):
    info = path.lstat()
    kind = stat.S_ISDIR if directory else stat.S_ISREG
    if not kind(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise StorageError('quota_untrusted_metadata')


def load(path):
    trusted(path)
    if path.stat().st_size > 65536:
        raise StorageError('quota_metadata_invalid')
    return json.loads(path.read_text())


def write(path, value):
    temporary = path.with_name(path.name+'.'+secrets.token_hex(8))
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


@contextlib.contextmanager
def locked():
    trusted(BASE, directory=True)
    fd = os.open(BASE/'.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if info.st_uid != 0 or not stat.S_ISREG(info.st_mode) or info.st_mode & 0o022:
            raise StorageError('quota_lock_untrusted')
        deadline = time.monotonic()+30
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() > deadline:
                    raise StorageError('quota_storage_busy')
                time.sleep(.1)
        yield
    finally:
        os.close(fd)


def register(state_dir):
    path = Path(state_dir).resolve(strict=True)
    info = path.stat()
    caller = int(os.environ.get('SUDO_UID', '0'))
    if not path.is_dir() or info.st_mode & 0o077 or (caller and caller != info.st_uid):
        raise StorageError('quota_registration_invalid')
    trusted(CONFIG.parent, directory=True)
    value = load(CONFIG) if CONFIG.exists() else {'workers': {}}
    namespace = hashlib.sha256(str(path).encode()).hexdigest()[:10]
    value['workers'][namespace] = {'state_dir': str(path), 'uid': info.st_uid}
    write(CONFIG, value)
    return {'registered': True, 'namespace': namespace}


def unregister(namespace):
    if not re.fullmatch('[a-f0-9]{10}', namespace or ''):
        raise StorageError('quota_binding_invalid')
    trusted(CONFIG.parent, directory=True)
    config = load(CONFIG)
    entry = config.get('workers', {}).get(namespace)
    caller = int(os.environ.get('SUDO_UID', '0'))
    if not entry or (caller and caller != entry['uid']):
        raise StorageError('quota_worker_not_authorized')
    if list(BASE.glob(namespace+'-*')):
        raise StorageError('quota_storage_in_use')
    del config['workers'][namespace]
    write(CONFIG, config)
    return {'unregistered': True}


def binding(namespace, owner):
    if not re.fullmatch('[a-f0-9]{10}', namespace or '') or not re.fullmatch('[a-z0-9][a-z0-9._-]{0,63}', owner or ''):
        raise StorageError('quota_binding_invalid')
    trusted(CONFIG.parent, directory=True)
    config = load(CONFIG)
    entry = config.get('workers', {}).get(namespace)
    if not entry or hashlib.sha256(entry['state_dir'].encode()).hexdigest()[:10] != namespace:
        raise StorageError('quota_worker_not_registered')
    caller = int(os.environ.get('SUDO_UID', '0'))
    if caller and caller != entry['uid']:
        raise StorageError('quota_worker_not_authorized')
    owner_hash = hashlib.sha256(owner.encode()).hexdigest()
    suffix = 'pilot' if owner == 'local-pilot' else 'user-'+owner_hash[:16]
    return BASE/(namespace+'-'+owner_hash), 'poc-managed-'+namespace+'-'+suffix+'-workspace', owner_hash


def manifest(namespace, owner):
    directory, volume, owner_hash = binding(namespace, owner)
    if not directory.exists():
        return directory, None
    trusted(directory, directory=True)
    if not (directory/'manifest.json').exists():
        raise StorageError('quota_provisioning_incomplete')
    data = load(directory/'manifest.json')
    if (data.get('namespace') != namespace or data.get('owner') != owner or data.get('volume') not in ({volume,volume+'-quota'} if data.get('legacy_volume')==volume else {volume})
            or not re.fullmatch('[a-f0-9]{32}', data.get('identity', '')) or data.get('quota_bytes') != QUOTA):
        raise StorageError('quota_manifest_invalid')
    return directory, data


def options(directory):
    return {'type': 'none', 'o': 'bind', 'device': str(directory/'mount/workspace')}


def labels(data):
    return {'poc.worker': data['namespace'], 'poc.owner': hashlib.sha256(data['owner'].encode()).hexdigest(),
            'poc.storage': BACKEND, 'poc.storage-id': data['identity']}


def volume_record(name):
    names = run('docker', 'volume', 'ls', '-q', '--filter', 'name='+name).splitlines()
    return json.loads(run('docker', 'volume', 'inspect', name))[0] if name in names else None


def validate_volume(directory, data, required=True):
    volume = volume_record(data['volume'])
    if volume is None:
        if required:
            raise StorageError('quota_volume_missing')
        return None
    if (volume.get('Name') != data['volume'] or volume.get('Driver') != 'local' or volume.get('Options') != options(directory)
            or any((volume.get('Labels') or {}).get(key) != value for key, value in labels(data).items())):
        raise StorageError('quota_volume_mismatch')
    return volume


def loop_for(directory, attach=False):
    image = directory/'data.xfs'
    trusted(image)
    info = image.stat()
    if info.st_size != IMAGE_BYTES:
        raise StorageError('quota_image_invalid')
    if info.st_blocks*512 < IMAGE_BYTES:
        raise StorageError('quota_image_reservation_missing')
    devices = json.loads(run('losetup', '--list', '--json', '--output', 'NAME,BACK-FILE'))['loopdevices']
    matches = [row['name'] for row in devices if row.get('back-file') == str(image)]
    if len(matches) > 1:
        raise StorageError('quota_loop_ambiguous')
    loop = matches[0] if matches else run('losetup', '--find', '--show', '--nooverlap', str(image)) if attach else None
    if loop is not None and not re.fullmatch('/dev/loop[0-9]+', loop):
        raise StorageError('quota_loop_invalid')
    return loop


def mount_record(directory):
    result = run('findmnt', '-J', '-M', str(directory/'mount'), '-o', 'SOURCE,FSTYPE,OPTIONS', absent=True)
    if result is None:
        return None
    rows = json.loads(result)['filesystems']
    if len(rows) != 1:
        raise StorageError('quota_mount_invalid')
    return rows[0]


def quota_command(directory, command):
    return run('xfs_quota', '-x', '-c', command, str(directory/'mount'))


def quota_values(report, device):
    rows = [line.split() for line in report.splitlines() if line.split() and line.split()[0] == device]
    if len(rows) != 1 or len(rows[0]) < 4 or not all(value.isdigit() for value in (rows[0][1], rows[0][3])):
        raise StorageError('quota_readback_invalid')
    return int(rows[0][1]), int(rows[0][3])


def validate_mount(directory, data):
    mounted = mount_record(directory)
    loop = loop_for(directory)
    if (not mounted or not loop or mounted['source'] != loop or mounted['fstype'] != 'xfs'
            or not {'rw', 'prjquota', 'nosuid', 'nodev'}.issubset(set(mounted['options'].split(',')))):
        raise StorageError('quota_mount_unavailable')
    if run('blkid', '-s', 'UUID', '-o', 'value', loop) != data['uuid']:
        raise StorageError('quota_filesystem_mismatch')
    state = quota_command(directory, 'state -p')
    if not re.search(r'Accounting:\s+ON', state) or not re.search(r'Enforcement:\s+ON', state):
        raise StorageError('quota_enforcement_unavailable')
    used, hard = quota_values(quota_command(directory, 'quota -p -b -N -v 1'), loop)
    if hard*1024 != QUOTA:
        raise StorageError('quota_limit_mismatch')
    workspace = directory/'mount/workspace'
    if workspace.is_symlink() or workspace.stat().st_uid != 10001 or workspace.stat().st_gid != 10001:
        raise StorageError('quota_workspace_invalid')
    attrs = run('xfs_io', '-r', '-c', 'stat', str(workspace))
    flags = re.search(r'fsxattr.xflags = 0x([a-fA-F0-9]+)', attrs)
    project = re.search(r'fsxattr.projid = ([0-9]+)', attrs)
    if not flags or not int(flags[1], 16) & 0x200 or not project or project[1] != '1':
        raise StorageError('quota_project_invalid')
    return used*1024


def restore(directory, data):
    if data['phase'] != 'ready':
        raise StorageError('quota_deletion_or_provisioning_incomplete')
    if mount_record(directory) is None:
        loop = loop_for(directory, attach=True)
        if run('blkid', '-s', 'UUID', '-o', 'value', loop) != data['uuid']:
            raise StorageError('quota_filesystem_mismatch')
        run('mount', '-t', 'xfs', '-o', 'prjquota,nosuid,nodev', loop, str(directory/'mount'))
    validate_mount(directory, data)


def create(namespace, owner, migration=False, alternate=False):
    directory, data = manifest(namespace, owner)
    if data is None:
        _, canonical, _ = binding(namespace, owner)
        name = canonical+'-quota' if migration or alternate else canonical
        if alternate and volume_record(canonical):raise StorageError('quota_migration_required')
        if volume_record(name):
            raise StorageError('quota_migration_required')
        if shutil.disk_usage(BASE).free < IMAGE_BYTES+RESERVE:
            raise StorageError('quota_pool_capacity')
        directory.mkdir(mode=0o700)
        (directory/'mount').mkdir(mode=0o700)
        data = {'namespace': namespace, 'owner': owner, 'volume': name, 'identity': secrets.token_hex(16),
                'phase': 'allocating', 'uuid': None, 'quota_bytes': QUOTA,
                'legacy_volume': canonical if migration or alternate else None, 'legacy_finalized':bool(alternate)}
        write(directory/'manifest.json', data)
        # Reserve guest disk capacity; never silently overcommit sparse images.
        fd = os.open(directory/'data.xfs', os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            os.posix_fallocate(fd, 0, IMAGE_BYTES)
            os.fsync(fd)
        finally:
            os.close(fd)
        run('mkfs.xfs', '-f', '-K', str(directory/'data.xfs'))
        loop = loop_for(directory, attach=True)
        run('mount', '-t', 'xfs', '-o', 'prjquota,nosuid,nodev', loop, str(directory/'mount'))
        workspace = directory/'mount/workspace'
        workspace.mkdir(mode=0o755)
        os.chown(workspace, 10001, 10001)
        quota_command(directory, f'project -s -p {workspace} 1')
        quota_command(directory, 'limit -p bhard=5g bsoft=0 ihard=100000 1')
        data.update(phase='ready', uuid=run('blkid', '-s', 'UUID', '-o', 'value', loop))
        validate_mount(directory, data)
        write(directory/'manifest.json', data)
    restore(directory, data)
    if validate_volume(directory, data, required=False) is None:
        arguments = ['docker', 'volume', 'create', '--driver', 'local']
        for key, value in labels(data).items():
            arguments += ['--label', key+'='+value]
        for key, value in options(directory).items():
            arguments += ['--opt', key+'='+value]
        run(*arguments, data['volume'])
    return status(namespace, owner)


def status(namespace, owner):
    directory, data = manifest(namespace, owner)
    if data is None:
        return {'state': 'absent'}
    if data['phase'] != 'ready':
        raise StorageError('quota_deletion_or_provisioning_incomplete')
    used = validate_mount(directory, data)
    validate_volume(directory, data)
    return {'state': 'ready', 'backend': BACKEND, 'identity': data['identity'], 'volume': data['volume'],
            'options': options(directory), 'hard_quota_enforced': True, 'quota_bytes': QUOTA,
            'quota_used_bytes': used, 'quota_remaining_bytes': max(0, QUOTA-used)}


def delete(namespace, owner, identity):
    directory, data = manifest(namespace, owner)
    if data is None or not secrets.compare_digest(data['identity'], identity or ''):
        raise StorageError('quota_identity_changed')
    if data['phase'] not in ('ready', 'deleting'):
        raise StorageError('quota_provisioning_incomplete')
    if data['phase'] == 'ready':
        validate_mount(directory, data)
    volume = validate_volume(directory, data, required=data['phase'] == 'ready')
    if run('docker', 'ps', '-aq', '--filter', 'volume='+data['volume']):
        raise StorageError('workspace_in_use')
    data['phase'] = 'deleting'
    write(directory/'manifest.json', data)  # Interrupted deletion must never resurrect old files on create.
    if volume:
        run('docker', 'volume', 'rm', data['volume'])
    loop = loop_for(directory) if (directory/'data.xfs').exists() else None
    mounted = mount_record(directory)
    if mounted:
        if not loop or mounted['source'] != loop or run('blkid', '-s', 'UUID', '-o', 'value', loop) != data['uuid']:
            raise StorageError('quota_filesystem_mismatch')
        run('umount', str(directory/'mount'))
    if loop:
        run('losetup', '-d', loop)
    (directory/'data.xfs').unlink(missing_ok=True)
    (directory/'manifest.json').unlink()
    (directory/'mount').rmdir()
    directory.rmdir()
    return {'deleted': True}


def legacy_source(namespace,owner):
    directory,name,owner_hash=binding(namespace,owner)
    volume=volume_record(name)
    if (not volume or volume.get('Name')!=name or volume.get('Driver')!='local' or volume.get('Options')
            or (volume.get('Labels') or {}).get('poc.worker')!=namespace
            or ((volume.get('Labels') or {}).get('poc.owner') not in (owner_hash,None) if owner=='local-pilot' else (volume.get('Labels') or {}).get('poc.owner')!=owner_hash)):
        raise StorageError('migration_source_invalid')
    if run('docker','ps','-aq','--filter','volume='+name):raise StorageError('workspace_in_use')
    docker_root=Path(run('docker','info','--format','{{.DockerRootDir}}'))
    path=Path(volume['Mountpoint'])
    if path.is_symlink() or path.resolve()!= (docker_root/'volumes'/name/'_data').resolve() or not path.is_dir():
        raise StorageError('migration_source_path_invalid')
    info=path.stat()
    if (info.st_uid,info.st_gid)!=(10001,10001):raise StorageError('migration_root_owner_unsupported')
    fingerprint=hashlib.sha256(json.dumps({key:volume.get(key) for key in ('Name','CreatedAt','Labels','Driver','Options')},sort_keys=True).encode()).hexdigest()
    return path,name,fingerprint


def migration_state(namespace,owner):
    from workspace_copy import inventory,CopyError
    source,name,source_id=legacy_source(namespace,owner)
    directory,data=manifest(namespace,owner)
    if not data or data.get('legacy_volume')!=name or data['phase'] not in ('ready','copying'):raise StorageError('migration_not_prepared')
    validate_mount(directory,data);validate_volume(directory,data)
    if run('docker','ps','-aq','--filter','volume='+data['volume']):raise StorageError('workspace_in_use')
    try:
        left=inventory(source);right=inventory(directory/'mount/workspace') if data['phase']=='ready' else None
    except CopyError as exc:raise StorageError(str(exc)) from None
    return {'phase':data['phase'],'identity':data['identity'],'source_volume':name,'target_volume':data['volume'],
            'source_identity':source_id,'source':left,'target':right,'copied_digest':data['migration_digest']}


def prepare_migration(namespace,owner):
    from workspace_copy import inventory,copy_verified,CopyError
    source,name,source_id=legacy_source(namespace,owner)
    try:before=inventory(source)
    except CopyError as exc:raise StorageError(str(exc)) from None
    directory,data=manifest(namespace,owner)
    if data is not None:
        current=migration_state(namespace,owner)
        if current['phase']!='ready':raise StorageError('migration_copy_incomplete')
        if current['source']['digest']!=current['copied_digest'] or current['target']['digest']!=current['copied_digest']:
            raise StorageError('migration_contents_changed')
        return current
    create(namespace,owner,migration=True)
    directory,data=manifest(namespace,owner)
    data.update(phase='copying',migration_digest=before['digest'],source_identity=source_id);write(directory/'manifest.json',data)
    try:
        verified=copy_verified(source,directory/'mount/workspace')
        if verified!=before:raise CopyError('migration_source_changed')
    except CopyError as exc:raise StorageError(str(exc)) from None
    data.update(phase='ready',migration_digest=verified['digest'],source_identity=source_id)
    write(directory/'manifest.json',data)
    return migration_state(namespace,owner)


def abort_migration(namespace,owner,identity):
    from workspace_copy import inventory
    directory,data=manifest(namespace,owner)
    source,name,source_id=legacy_source(namespace,owner)
    if (not data or data.get('phase') not in ('copying','ready') or data.get('identity')!=identity
            or data.get('legacy_volume')!=name or data.get('source_identity')!=source_id
            or inventory(source)['digest']!=data.get('migration_digest')):
        raise StorageError('migration_abort_refused')
    if data['phase']=='ready' and inventory(directory/'mount/workspace')['digest']!=data.get('migration_digest'):
        raise StorageError('migration_abort_refused')
    data['phase']='deleting';write(directory/'manifest.json',data)
    return delete(namespace,owner,identity)


def finalize_migration(namespace,owner,identity):
    from workspace_copy import inventory
    directory,data=manifest(namespace,owner)
    _,canonical,_=binding(namespace,owner)
    if not data or data.get('phase')!='ready' or data.get('identity')!=identity or data.get('legacy_volume')!=canonical:
        raise StorageError('migration_identity_changed')
    validate_mount(directory,data);validate_volume(directory,data)
    if run('docker','ps','-aq','--filter','volume='+data['volume']):raise StorageError('workspace_in_use')
    if volume_record(canonical) is not None:
        source,name,source_id=legacy_source(namespace,owner)
        if source_id!=data.get('source_identity') or inventory(source)['digest']!=data.get('migration_digest'):
            raise StorageError('migration_source_changed')
        data['migration_finalizing']=True;write(directory/'manifest.json',data)
        run('docker','volume','rm',canonical)
    elif not data.get('migration_finalizing') and not data.get('legacy_finalized'):
        raise StorageError('migration_backup_missing')
    if volume_record(canonical) is not None:raise StorageError('migration_finalize_unverified')
    data['legacy_finalized']=True;write(directory/'manifest.json',data)
    return {'finalized':True,'identity':data['identity']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['register', 'unregister', 'restore-all', 'status', 'create', 'delete', 'prepare-migration', 'migration-state', 'abort-migration', 'finalize-migration', 'create-migrated'])
    parser.add_argument('namespace', nargs='?')
    parser.add_argument('owner', nargs='?')
    parser.add_argument('--state-dir')
    parser.add_argument('--identity')
    args = parser.parse_args()
    if os.geteuid() != 0 or sys.platform != 'linux':
        raise SystemExit('Requires Linux root')
    os.environ['PATH'] = '/usr/sbin:/usr/bin:/sbin:/bin'
    os.umask(0o077)
    try:
        with locked():
            if args.action == 'register':
                result = register(args.state_dir)
            elif args.action == 'unregister':
                result = unregister(args.namespace)
            elif args.action == 'restore-all':
                restored = 0
                incomplete = 0
                for path in BASE.glob('*/manifest.json'):
                    data = load(path)
                    directory, expected = manifest(data['namespace'], data['owner'])
                    if directory != path.parent or expected != data:
                        raise StorageError('quota_manifest_invalid')
                    if data['phase'] != 'ready':
                        incomplete += 1
                        continue
                    restore(directory, data)
                    restored += 1
                result = {'restored': restored, 'incomplete': incomplete}
            else:
                result = {'status': status, 'create': create, 'create-migrated':lambda ns,owner:create(ns,owner,alternate=True), 'prepare-migration':prepare_migration, 'migration-state':migration_state, 'abort-migration':lambda ns,owner:abort_migration(ns,owner,args.identity), 'finalize-migration':lambda ns,owner:finalize_migration(ns,owner,args.identity), 'delete': lambda ns, owner: delete(ns, owner, args.identity)}[args.action](args.namespace, args.owner)
        print(json.dumps(result))
    except Exception as exc:
        code = str(exc) if isinstance(exc, StorageError) else 'quota_storage_unavailable'
        print(json.dumps({'error': code}), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

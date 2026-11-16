#!/usr/bin/env python3
"""Opt-in root-only disposable XFS quota validation inside lima-gvisor-poc.

Never imports worker state, migrates a workspace, or edits fstab/root FS features.
Requires >=9 GiB free VM space; temporarily allocates just under 5 GiB.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
import time
import uuid

GIB = 1024**3
LIMIT = 5 * GIB
AGENT = 'sha256:1c699e85c4765335983513403bc9edb812ffcc88dab0f9132274406079fdee5a'
RUNTIME = 'runsc-stable-20261109'


def run(*args, check=True, timeout=30):
    result = subprocess.run(args, text=True, capture_output=True, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError('command_failed:' + Path(args[0]).name + ':' + result.stderr.strip()[:400])
    return result


def hard_limit_kib(report, device):
    """Quota output is filesystem-row based; absent/ambiguous rows fail closed."""
    rows = [line.split() for line in report.splitlines() if line.split() and line.split()[0] == device]
    return int(rows[0][3]) if len(rows) == 1 and len(rows[0]) >= 4 and rows[0][3].isdigit() else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-disposable-storage-test', action='store_true')
    args = parser.parse_args()
    if not args.allow_disposable_storage_test or os.geteuid() != 0 or os.uname().nodename != 'lima-gvisor-poc':
        raise SystemExit('Requires explicit opt-in as root inside lima-gvisor-poc only')
    for name in ('docker', 'mkfs.xfs', 'xfs_quota', 'losetup', 'mount', 'umount', 'findmnt'):
        if not shutil.which(name):
            raise SystemExit('Missing tool: ' + name)
    if shutil.disk_usage('/var/tmp').free < 9 * GIB:
        raise SystemExit('Requires at least 9 GiB free VM storage')
    run('docker', 'image', 'inspect', AGENT)
    runtimes = json.loads(run('docker', 'info', '--format', '{{json .Runtimes}}').stdout)
    if RUNTIME not in runtimes:
        raise SystemExit('Pinned runsc runtime unavailable')
    tag = uuid.uuid4().hex
    root = Path(tempfile.mkdtemp(prefix='gvisor-quota-test-', dir='/var/tmp'))
    root.chmod(0o700)
    image = root / 'disposable.xfs'
    mount = root / 'mount'
    mount.mkdir()
    loop = None
    mounted = False
    volumes = []
    container = 'poc-quota-test-' + tag
    checks = {}
    measurements = {}
    error = None
    cleanup_errors = []
    started = time.monotonic()

    def quota(command):
        result = run('xfs_quota', '-x', '-c', command, str(mount))
        measurements.setdefault('quota_diagnostics', []).append({'command':command.replace(str(mount),'<fixture-mount>'), 'stdout':result.stdout.strip(), 'stderr':result.stderr.strip()})
        return result.stdout

    def probe(volume, command):
        result = run('docker', 'run', '--rm', '--name', container, '--pull=never',
            '--label', 'poc.quota-test='+tag, '--runtime='+RUNTIME, '--network=none',
            '--read-only', '--user=10001:10001', '--cpus=1', '--memory=128m',
            '--pids-limit=32', '--cap-drop=ALL', '--security-opt=no-new-privileges',
            '--mount', 'type=volume,source='+volume+',target=/workspace',
            '--entrypoint='+command[0], AGENT, *command[1:], check=False, timeout=90)
        measurements.setdefault('probe_diagnostics', []).append({'exit':result.returncode,'stderr':result.stderr.strip()[:400]})
        return result

    def make_volume(index):
        name = 'poc-quota-test-' + tag + '-' + index
        run('docker', 'volume', 'create', '--label', 'poc.quota-test='+tag,
            '--driver', 'local', '--opt', 'type=none', '--opt', 'o=bind',
            '--opt', 'device='+str(mount / index), name)
        volumes.append(name)
        return name

    def remove_volumes():
        while volumes:
            name = volumes[-1]
            item = json.loads(run('docker', 'volume', 'inspect', name).stdout)[0]
            if item.get('Labels', {}).get('poc.quota-test') != tag:
                raise RuntimeError('refusing_foreign_volume_cleanup')
            run('docker', 'volume', 'rm', name)
            volumes.pop()

    try:
        with image.open('xb') as stream:
            stream.truncate(6 * GIB)
        image.chmod(0o600)
        run('mkfs.xfs', '-f', str(image))
        loop = run('losetup', '--find', '--show', '--nooverlap', str(image)).stdout.strip()
        if not re.fullmatch('/dev/loop[0-9]+', loop):
            raise RuntimeError('unexpected_loop_device')
        run('mount', '-t', 'xfs', '-o', 'prjquota,nosuid,nodev', loop, str(mount))
        mounted = True
        for index, project, budget in [('a', 1001, '5g'), ('b', 1002, '32m')]:
            directory = mount / index
            directory.mkdir()
            os.chown(directory, 10001, 10001)
            quota(f'project -s -p {directory} {project}')
            quota(f'limit -p bhard={budget} bsoft=0 ihard=100000 {project}')
        state = quota('state -p')
        checks['project_enforcement_on'] = bool(re.search(r'Enforcement:\s+ON', state))
        report = quota('quota -p -b -N -v 1001')
        measurements['project_a_quota_report'] = report.strip()
        # Default xfs_quota block report uses KiB; require actual numeric readback.
        checks['configured_5_gib_hard_limit'] = hard_limit_kib(report, loop) == LIMIT // 1024
        a, b = make_volume('a'), make_volume('b')
        def node(volume, code):
            return probe(volume, ['node', '--max-old-space-size=32', '-e', code])
        marker = node(a, "const fs=require('fs');fs.writeFileSync('/workspace/marker','retained');fs.mkdirSync('/workspace/nested');if(fs.readFileSync('/workspace/marker','utf8')!=='retained')process.exit(1)")
        checks['nonroot_workspace_write'] = marker.returncode == 0
        first = probe(a, ['fallocate','-l',str(3*GIB),'/workspace/one'])
        second = probe(a, ['fallocate','-l',str(2*GIB-8*1024**2),'/workspace/nested/two'])
        checks['multiple_files_near_5_gib'] = first.returncode == second.returncode == 0
        checks['allocated_blocks_near_limit'] = sum(os.stat(mount/path).st_blocks*512 for path in ('a/one','a/nested/two')) >= LIMIT-8*1024**2
        checks['filesystem_has_headroom'] = shutil.disk_usage(mount).free > 512*1024**2
        overflow = probe(a, ['fallocate','-l','16777216','/workspace/nested/overflow'])
        checks['gvisor_over_limit_denied'] = overflow.returncode != 0 and any(message in overflow.stderr for message in ('Disk quota exceeded','No space left on device'))
        measurements['gvisor_over_limit_error'] = overflow.stderr.strip()
        # Open only this generated file as root, then drop privileges before allocating.
        code = "import os,errno,json;fd=os.open("+repr(str(mount/'a/host-overflow'))+",os.O_CREAT|os.O_RDWR,0o600);os.fchown(fd,10001,10001);os.setgid(10001);os.setuid(10001)\ntry:os.posix_fallocate(fd,0,16777216);result=0\nexcept OSError as exc:result=exc.errno\nfinally:os.close(fd)\nprint(json.dumps({'errno':result}))"
        host_result = json.loads(run('python3','-c',code).stdout)
        measurements['host_over_limit_errno'] = host_result['errno']
        import errno
        # XFS project quota exhaustion uses ENOSPC (XFS_QMOPT_ENOSPC).
        checks['host_confirms_project_limit'] = host_result['errno'] == errno.ENOSPC
        writes = node(a, "const fs=require('fs');const fd=fs.openSync('/workspace/write-overflow','w');const buffer=Buffer.alloc(1048576);let total=0,denied=null;try{for(let n=0;n<16;n++)total+=fs.writeSync(fd,buffer);fs.fsyncSync(fd)}catch(error){denied=error.code}finally{fs.closeSync(fd)}console.log(JSON.stringify({denied,bytes_written:total}));process.exit(denied==='ENOSPC'?0:1)")
        write_result = json.loads(writes.stdout) if writes.stdout.strip() else {}
        measurements['write_exhaustion'] = write_result
        checks['actual_writes_enforce_limit'] = writes.returncode == 0 and write_result.get('denied') == 'ENOSPC'
        checks['other_project_same_uid_writable'] = probe(b, ['fallocate','-l','1048576','/workspace/independent']).returncode == 0
        overflow_b = probe(b, ['fallocate','-l','33554432','/workspace/overflow'])
        checks['second_project_limit_enforced'] = overflow_b.returncode != 0 and any(message in overflow_b.stderr for message in ('Disk quota exceeded','No space left on device'))
        freed = node(a, "const fs=require('fs');for(const name of ['one','nested/two','nested/overflow','host-overflow','write-overflow'])fs.rmSync('/workspace/'+name,{force:true})")
        checks['freeing_space_recovers_writes'] = freed.returncode == 0 and probe(a, ['fallocate','-l','1048576','/workspace/recovered']).returncode == 0
        remove_volumes()
        run('umount', str(mount))
        mounted = False
        run('mount', '-t', 'xfs', '-o', 'prjquota,nosuid,nodev', loop, str(mount))
        mounted = True
        report = quota('quota -p -b -N -v 1001')
        checks['hard_limit_survives_remount'] = hard_limit_kib(report, loop) == LIMIT // 1024
        a = make_volume('a')
        checks['data_survives_remount'] = node(a, "const fs=require('fs');if(fs.readFileSync('/workspace/marker','utf8')!=='retained'||!fs.existsSync('/workspace/recovered'))process.exit(1)").returncode == 0
        overflow_after = probe(a, ['fallocate','-l',str(LIMIT),'/workspace/too-large'])
        checks['enforcement_survives_remount'] = overflow_after.returncode != 0 and any(message in overflow_after.stderr for message in ('Disk quota exceeded','No space left on device'))
        if not all(checks.values()):
            raise RuntimeError('quota_acceptance_check_failed')
    except BaseException as exc:
        error = str(exc)[:500] or type(exc).__name__
    finally:
        try:
            run('docker', 'rm', '-f', container, check=False)
            remove_volumes()
        except Exception as exc:
            cleanup_errors.append(str(exc)[:300])
        # Inspect actual mount state, including a mount command interrupted after success.
        try:
            observed = run('findmnt', '-rn', '-M', str(mount), '-o', 'SOURCE', check=False)
            if observed.returncode not in (0, 1):
                raise RuntimeError('mount_state_unknown')
            mounted = observed.returncode == 0
        except Exception as exc:
            mounted = True  # Unknown mount state forbids detach/removal.
            cleanup_errors.append(str(exc)[:300])
        if mounted:
            try:
                source = run('findmnt', '-rn', '-M', str(mount), '-o', 'SOURCE').stdout.strip()
                if source != loop:
                    raise RuntimeError('refusing_unexpected_mount_cleanup')
                run('umount', str(mount))
                mounted = False
            except Exception as exc:
                cleanup_errors.append(str(exc)[:300])
        if loop and not mounted:
            try:
                devices = json.loads(run('losetup', '--list', '--json', '--output', 'NAME,BACK-FILE', loop).stdout)['loopdevices']
                if len(devices) != 1 or devices[0]['back-file'] != str(image):
                    raise RuntimeError('refusing_unexpected_loop_cleanup')
                run('losetup', '-d', loop)
                loop = None
            except Exception as exc:
                cleanup_errors.append(str(exc)[:300])
        if not mounted and loop is None and not volumes:
            shutil.rmtree(root)
        checks['disposable_storage_cleaned'] = not root.exists() and not cleanup_errors
    output = {'checks': checks, 'passed': error is None and all(checks.values()),
        'hard_limit_bytes': LIMIT, 'candidate_only': True, 'pilot_hard_quota_enabled': False,
        'user_workspace_read': False, 'user_workspace_changed': False,
        'elapsed_seconds': round(time.monotonic()-started, 3), 'measurements': measurements,
        'error': error, 'cleanup_errors': cleanup_errors}
    print(json.dumps(output, indent=2))
    return 0 if output['passed'] else 1


if __name__ == '__main__':
    def interrupted(*_args):
        raise KeyboardInterrupt('interrupted; attempting disposable-storage cleanup')
    signal.signal(signal.SIGTERM, interrupted)
    raise SystemExit(main())

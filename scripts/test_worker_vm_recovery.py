#!/usr/bin/env python3
"""Explicit isolated prepare/verify/cleanup phases across an operator-run VM restart."""
import argparse
import json
import pathlib
import shutil
import subprocess
import time
from manage_codex_session import Worker

ROOT = pathlib.Path(__file__).resolve().parent.parent
UNIT = 'gvisor-poc-recovery-check.service'
STATE = pathlib.Path.home() / '.local/state/gvisor-poc-recovery-check'
UNIT_FILE = pathlib.Path.home() / '.config/systemd/user' / UNIT


def ctl(*args):
    return subprocess.check_output(['systemctl', '--user', *args], text=True, stderr=subprocess.STDOUT, timeout=30).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['prepare', 'verify', 'cleanup'])
    args = parser.parse_args()
    if args.phase == 'prepare' and (STATE.exists() or UNIT_FILE.exists()):
        raise SystemExit('refusing_to_overwrite_existing_recovery_check')
    if args.phase != 'prepare' and not (STATE / 'fixture.json').exists():
        raise SystemExit('recovery_fixture_missing')
    worker = Worker(STATE)
    if args.phase == 'prepare':
        # Unit is enabled but not started until boot. No console uses this namespace.
        with worker.locked():
            overdue = worker.create('recovery-overdue')
            live = worker.create('recovery-unexpired')
            worker.db.execute('UPDATE sessions SET expires=? WHERE id=?', (time.time() - 1, overdue['id']))
            worker.db.commit()
        worker.docker('exec', worker.names(live['id'])['agent'], 'sh', '-c', 'printf VM_RECOVERY_OK > /workspace/recovery-marker')
        fixture = {'overdue': overdue['id'], 'unexpired': live['id'],
                   'boot_id': pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
        (STATE / 'fixture.json').write_text(json.dumps(fixture))
        template = (ROOT / 'deploy/systemd/gvisor-poc-reconciler.service').read_text()
        template = template.replace('ExecStart=/usr/bin/python3 %h/gvisor-managed-pilot/scripts/run_worker_reconciler.py',
                                    f'ExecStart=/usr/bin/python3 {ROOT}/scripts/run_worker_reconciler.py --state-dir {STATE} --interval 2')
        UNIT_FILE.write_text(template)
        ctl('daemon-reload')
        ctl('enable', UNIT)
        print(json.dumps({'prepared': True, 'isolated_state': str(STATE), 'test_unit_enabled_not_started': True}))
    elif args.phase == 'verify':
        fixture = json.loads((STATE / 'fixture.json').read_text())
        checks = {'vm_boot_changed': pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip() != fixture['boot_id']}
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if worker.get(fixture['overdue'])['state'] == 'stopped' and worker.get(fixture['unexpired'])['state'] == 'failed':
                break
            time.sleep(1)
        checks['test_service_started_on_boot'] = ctl('is-active', UNIT) == 'active'
        checks['pilot_service_started_on_boot'] = ctl('is-active', 'gvisor-poc-reconciler.service') == 'active'
        health = json.loads((STATE / 'reconciler-health.json').read_text())
        checks['fresh_successful_sweep'] = not health['error'] and bool(health['last_success']) and time.time() - health['last_success'] < 15
        overdue, lost = worker.get(fixture['overdue']), worker.get(fixture['unexpired'])
        checks['overdue_cleaned_after_boot'] = overdue['state'] == 'stopped' and overdue['stop_reason'] == 'expired'
        checks['unexpired_stopped_container_invalidated'] = lost['state'] == 'failed' and lost['failure'] == 'resource_lost'
        checks['test_resources_removed'] = all(worker.exists(kind, worker.names(sid)[key]) is None
            for sid in [fixture['overdue'], fixture['unexpired']]
            for kind, key in [('container', 'agent'), ('container', 'gateway'), ('network', 'internal'), ('network', 'egress')])
        with worker.locked():
            replacement = worker.create('recovery-replacement')
        checks['workspace_data_survives_vm_restart'] = worker.docker('exec', worker.names(replacement['id'])['agent'], 'cat', '/workspace/recovery-marker') == 'VM_RECOVERY_OK'
        checks['replacement_has_no_login_home'] = subprocess.run(['docker', 'exec', worker.names(replacement['id'])['agent'], 'test', '-e', '/home/agent/.codex/auth.json'], capture_output=True).returncode == 1
        result = {'passed': all(checks.values()), 'checks': checks, 'scope': 'actual Lima VM stop/start; isolated synthetic sessions; no model calls; no Mac sleep test'}
        (STATE / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, indent=2))
        if not result['passed']:
            raise SystemExit(1)
    else:
        ctl('disable', '--now', UNIT)
        UNIT_FILE.unlink()
        ctl('daemon-reload')
        for row in worker.db.execute('SELECT id FROM sessions').fetchall():
            with worker.locked():
                worker.stop(row['id'])
        obj = worker.exists('volume', worker.volume)
        if obj:
            worker.ensure_owned(obj)
            worker.docker('volume', 'rm', worker.volume)
        worker.db.close()
        shutil.rmtree(STATE)
        print(json.dumps({'isolated_test_resources_removed': True}))


if __name__ == '__main__':
    main()

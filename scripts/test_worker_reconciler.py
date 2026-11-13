#!/usr/bin/env python3
"""Isolated real systemd-user-service tests; no production session or model traffic."""
import argparse
import json
import os
import pathlib
import re
import shutil
import signal
import subprocess
import time
import uuid
from manage_codex_session import Worker

ROOT = pathlib.Path(__file__).resolve().parent.parent


def systemctl(*args):
    return subprocess.check_output(['systemctl', '--user', *args], text=True, stderr=subprocess.STDOUT, timeout=20).strip()


def wait_for(predicate, timeout=15):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        if predicate():
            return True
        time.sleep(.1)
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    output = pathlib.Path(parser.parse_args().output)
    tag = uuid.uuid4().hex[:12]
    state = pathlib.Path.home() / '.local/state' / ('poc-reconciler-test-' + tag)
    worker = Worker(state)
    source = state / 'source'
    source.mkdir()
    for name in ['manage_codex_session.py', 'run_worker_reconciler.py', 'security_history.py', 'console_observability.py']:
        shutil.copyfile(ROOT / 'scripts' / name, source / name)
    unit = 'gvisor-poc-reconciler-test-' + tag + '.service'
    unit_file = pathlib.Path.home() / '.config/systemd/user' / unit
    unit_file.parent.mkdir(parents=True, exist_ok=True)
    template = (ROOT / 'deploy/systemd/gvisor-poc-reconciler.service').read_text()
    template = re.sub(r'^ExecStart=.*$', f'ExecStart=/usr/bin/python3 {source}/run_worker_reconciler.py --state-dir {state} --interval 0.2', template, flags=re.M)
    template = template.replace('ReadWritePaths=%h/.local/state/gvisor-poc-worker', f'ReadWritePaths={state}')
    checks = {}

    def health():
        try:
            return json.loads((state / 'reconciler-health.json').read_text())
        except (OSError, ValueError):
            return {}

    try:
        with worker.locked():
            row = worker.create('resident-first')
        worker.docker('exec', worker.names(row['id'])['agent'], 'sh', '-c', 'printf RESIDENT_OK > /workspace/resident-marker')
        unit_file.write_text(template)
        subprocess.run(['systemd-analyze', '--user', 'verify', str(unit_file)], check=True, capture_output=True)
        checks['unit_validated'] = True
        systemctl('daemon-reload')
        systemctl('start', unit)
        checks['service_healthy'] = wait_for(lambda: health().get('last_success') is not None)
        if not checks['service_healthy']:
            raise RuntimeError('isolated reconciler did not become healthy')
        checks['health_private'] = (state / 'reconciler-health.json').stat().st_mode & 0o777 == 0o600
        with worker.locked():
            worker.db.execute('UPDATE sessions SET expires=? WHERE id=?', (time.time() - 1, row['id']))
            worker.db.commit()
        checks['resident_expiry_without_console'] = wait_for(lambda: worker.get(row['id'])['state'] == 'stopped')
        checks['expiry_reason'] = worker.get(row['id'])['stop_reason'] == 'expired'
        checks['temporary_container_removed'] = worker.exists('container', worker.names(row['id'])['agent']) is None
        checks['workspace_volume_retained'] = worker.exists('volume', worker.volume) is not None
        pid = int(systemctl('show', unit, '-p', 'MainPID', '--value'))
        before = time.time()
        os.kill(pid, signal.SIGKILL)
        checks['supervised_restart'] = wait_for(lambda: int(systemctl('show', unit, '-p', 'MainPID', '--value')) not in (0, pid) and (health().get('last_success') or 0) > before)
        systemctl('stop', unit)
        # Fail only this test service's Docker connection, not the real Docker daemon.
        unit_file.write_text(template.replace('unix:///var/run/docker.sock', 'unix:///nonexistent-poc-test.sock'))
        systemctl('daemon-reload')
        systemctl('start', unit)
        checks['docker_failure_reported'] = wait_for(lambda: health().get('error') == 'worker_unavailable_or_cleanup_failed')
        systemctl('stop', unit)
        unit_file.write_text(template)
        systemctl('daemon-reload')
        systemctl('start', unit)
        checks['recovery_after_docker_connection_restore'] = wait_for(lambda: health().get('error') is None and (health().get('last_success') or 0) > before)
        with worker.locked():
            replacement = worker.create('resident-replacement')
        checks['workspace_data_survives'] = worker.docker('exec', worker.names(replacement['id'])['agent'], 'cat', '/workspace/resident-marker') == 'RESIDENT_OK'
    finally:
        try:
            systemctl('stop', unit)
        finally:
            unit_file.unlink(missing_ok=True)
            systemctl('daemon-reload')
            systemctl('reset-failed', unit) if subprocess.run(['systemctl', '--user', 'is-failed', unit], capture_output=True).returncode == 0 else None
            for row in worker.db.execute('SELECT id FROM sessions').fetchall():
                with worker.locked():
                    worker.stop(row['id'])
            volume = worker.exists('volume', worker.volume)
            if volume:
                worker.ensure_owned(volume)
                worker.docker('volume', 'rm', worker.volume)
            worker.db.close()
            shutil.rmtree(state)
    result = {'passed': all(checks.values()), 'checks': checks,
              'scope': 'real isolated systemd user unit with production sandbox settings; injected past deadline; no browser/backend requests; no VM reboot test'}
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    if not result['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()

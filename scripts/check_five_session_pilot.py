#!/usr/bin/env python3
"""Single-account, five-session pilot check; device login remains private and interactive."""
import argparse
import concurrent.futures
import json
import pathlib
import subprocess
import sys
import time
import uuid
from manage_codex_session import Worker

ROOT = pathlib.Path(__file__).resolve().parent
FIXTURE = pathlib.Path.home() / '.local/state/gvisor-poc-five-session-check.json'
WORKER_STATE = '~/.local/state/gvisor-poc-worker'


def create(key):
    begin = time.monotonic()
    result = subprocess.run([sys.executable, str(ROOT / 'manage_codex_session.py'), 'create', '--key', key], capture_output=True, text=True, timeout=180)
    if result.returncode:
        return {'key': key, 'error': 'create_failed', 'seconds': round(time.monotonic() - begin, 3)}
    row = json.loads(result.stdout)
    return {'id': row['id'], 'state': row['state'], 'expires': row['expires'], 'seconds': round(time.monotonic() - begin, 3)}


def probe(row):
    worker = Worker(WORKER_STATE)
    name = worker.names(row['id'])['agent']
    begin = time.monotonic()
    result = {'id': row['id'], 'passed': False, 'error_events': 0, 'turn_completed': False, 'expected_reply': False}
    try:
        process = subprocess.run(['docker', 'exec', name, 'codex', '--no-daemon', 'exec',
                                  '--sandbox', 'workspace-write', '--skip-git-repo-check', '--ephemeral', '--json',
                                  'Reply with exactly PILOT_READY_OK. Do not use tools or read or modify files.'],
                                 text=True, capture_output=True, timeout=180)
        result['exit_code'] = process.returncode
        for line in process.stdout.splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get('type') in ('error', 'turn.failed'):
                result['error_events'] += 1
            if event.get('type') == 'turn.completed':
                result['turn_completed'] = True
            item = event.get('item') or {}
            if item.get('type') == 'agent_message' and item.get('text', '').strip() == 'PILOT_READY_OK':
                result['expected_reply'] = True
        result['passed'] = process.returncode == 0 and result['turn_completed'] and result['expected_reply'] and not result['error_events']
    except subprocess.TimeoutExpired:
        result['failure'] = 'probe_timeout'
    finally:
        worker.db.close()
    result['seconds'] = round(time.monotonic() - begin, 3)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['prepare', 'login', 'status', 'probe', 'stop'])
    args = parser.parse_args()
    worker = Worker(WORKER_STATE)
    if args.phase == 'prepare':
        if FIXTURE.exists():
            raise SystemExit('existing_five_session_fixture_requires_review')
        if worker.db.execute("SELECT COUNT(*) FROM sessions WHERE state IN ('ready','provisioning','stopping')").fetchone()[0]:
            raise SystemExit('active_pilot_sessions_present')
        tag = uuid.uuid4().hex
        # Save intended keys before mutations so an interrupted preparation is recoverable.
        fixture = {'keys': [f'five-check-{tag}-{i}' for i in range(5)], 'sessions': [], 'prepared_at': time.time()}
        FIXTURE.write_text(json.dumps(fixture)); FIXTURE.chmod(0o600)
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            fixture['sessions'] = list(pool.map(create, fixture['keys']))
        FIXTURE.write_text(json.dumps(fixture, indent=2) + '\n')
        print(json.dumps({'login_ready': all(s.get('state') == 'ready' for s in fixture['sessions']), 'sessions': fixture['sessions'],
                          'scope': 'one batch; cached images; CLI request-to-login-ready includes queue; no authentication/model readiness or reliable p95 estimate'}, indent=2))
    else:
        fixture = json.loads(FIXTURE.read_text())
        if args.phase == 'login':
            if not sys.stdin.isatty():
                raise SystemExit('interactive_terminal_required')
            for index, row in enumerate(fixture['sessions'], 1):
                print(f'Private device login {index}/5', flush=True)
                name = worker.names(row['id'])['agent']
                status = subprocess.run(['docker', 'exec', name, 'codex', '--no-daemon', 'login', 'status'], capture_output=True, timeout=30)
                if status.returncode == 0:
                    print('Login already verified; continuing.', flush=True)
                    continue
                rc = subprocess.call([sys.executable, str(ROOT / 'manage_codex_session.py'), 'login', row['id']])
                if rc:
                    raise SystemExit(rc)
                status = subprocess.run(['docker', 'exec', name, 'codex', '--no-daemon', 'login', 'status'], capture_output=True, timeout=30)
                if status.returncode:
                    raise SystemExit('Login did not persist in this session; stop and report the non-secret error.')
                print(f'Login {index}/5 verified.', flush=True)
        elif args.phase == 'probe':
            if len(fixture['sessions']) != 5 or any(worker.get(row['id'])['state'] != 'ready' for row in fixture['sessions']):
                raise SystemExit('five_ready_sessions_required')
            for row in fixture['sessions']:
                status = subprocess.run(['docker', 'exec', worker.names(row['id'])['agent'], 'codex', 'login', 'status'], capture_output=True, timeout=30)
                if status.returncode:
                    raise SystemExit('private_login_required_in_all_five_sessions')
            begin = time.monotonic()
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
                probes = list(pool.map(probe, fixture['sessions']))
            result = {'passed': all(p['passed'] for p in probes), 'probes': probes,
                      'batch_seconds': round(time.monotonic() - begin, 3),
                      'scope': 'five concurrent sessions on one account; fixed reply-only model task after manual login; excludes provisioning and human login; five observations are not a reliable p95 estimate'}
            (FIXTURE.parent / 'gvisor-poc-five-session-result.json').write_text(json.dumps(result, indent=2) + '\n')
            print(json.dumps(result, indent=2))
            if not result['passed']:
                raise SystemExit(1)
        elif args.phase == 'status':
            output = []
            for row in fixture['sessions']:
                current = worker.get(row['id'])
                status = subprocess.run(['docker', 'exec', worker.names(row['id'])['agent'], 'codex', 'login', 'status'], capture_output=True, timeout=30)
                output.append({'id': row['id'], 'state': current['state'], 'logged_in': status.returncode == 0})
            print(json.dumps(output, indent=2))
        else:
            # Resolve intended keys so interrupted preparation can still be cleaned.
            import hashlib
            for key in fixture['keys']:
                row = worker.db.execute('SELECT id FROM sessions WHERE request_key=?', (hashlib.sha256(key.encode()).hexdigest(),)).fetchone()
                if row:
                    with worker.locked():
                        worker.stop(row['id'])
            FIXTURE.unlink()
            print(json.dumps({'test_sessions_stopped_workspace_retained': True}))


if __name__ == '__main__':
    main()

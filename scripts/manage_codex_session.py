#!/usr/bin/env python3
"""Trusted local worker CLI. Run inside Linux VM; not a remote service/API."""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import pathlib
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import uuid

ROOT = pathlib.Path(__file__).resolve().parent.parent
AGENT = 'sha256:1c699e85c4765335983513403bc9edb812ffcc88dab0f9132274406079fdee5a'
GATEWAY = 'mitmproxy/mitmproxy:12.3.1@sha256:2711066c855659b5af8b1dbb84494ed3eff69b42ece439c60b4fe09a2db829d4'
RUNTIME = 'runsc-stable-20261109'
SESSION_LIFETIME_SECONDS = 3600
CONFIG = '''model_provider = "poc_https"
[model_providers.poc_https]
name = "OpenAI HTTPS through POC gateway"
base_url = "https://chatgpt.com/backend-api/codex"
wire_api = "responses"
requires_openai_auth = true
supports_websockets = false
'''


class WorkerError(Exception):
    pass


class Worker:
    def __init__(self, state):
        self.root = pathlib.Path(state).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)
        self.namespace = hashlib.sha256(str(self.root).encode()).hexdigest()[:10]
        self.volume = f'poc-managed-{self.namespace}-pilot-workspace'
        self.label = f'poc.worker={self.namespace}'
        self.db = sqlite3.connect(self.root / 'sessions.sqlite', timeout=120)
        os.chmod(self.root / 'sessions.sqlite', 0o600)
        self.db.row_factory = sqlite3.Row
        with self.locked():
            self.db.execute('CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, request_key TEXT UNIQUE, state TEXT, created REAL, ready REAL, stopped REAL, failure TEXT)')
            columns = {row[1] for row in self.db.execute('PRAGMA table_info(sessions)')}
            for name, kind in [('expires', 'REAL'), ('stop_reason', 'TEXT')]:
                if name not in columns:
                    self.db.execute(f'ALTER TABLE sessions ADD COLUMN {name} {kind}')
            self.db.execute('CREATE TABLE IF NOT EXISTS events (sequence INTEGER PRIMARY KEY, session_id TEXT, action TEXT, state TEXT, at REAL)')
            self.db.commit()
            from security_history import initialize
            initialize(self.db)

    @contextlib.contextmanager
    def locked(self):
        with (self.root / 'worker.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    def docker(self, *args, input=None):
        try:
            result = subprocess.run(['docker', *args], input=input, text=True, capture_output=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            raise WorkerError('docker_unavailable_or_timeout') from None
        if result.returncode:
            # CLI stderr may contain request data. Return a fixed safe error code.
            raise WorkerError('docker_operation_failed')
        return result.stdout.strip()

    def exists(self, kind, name):
        result = subprocess.run(['docker', kind, 'inspect', name], capture_output=True, text=True, timeout=10)
        if result.returncode:
            # Distinguish an unavailable daemon from an absent resource.
            self.docker('info', '--format', '{{.ServerVersion}}')
            return None
        return json.loads(result.stdout)[0]

    def names(self, sid):
        if not re.fullmatch('[a-f0-9]{32}', sid):
            raise WorkerError('invalid_session_id')
        base = f'poc-managed-{self.namespace}-{sid}'
        return {'agent': base + '-agent', 'gateway': base + '-gateway',
                'internal': base + '-internal', 'egress': base + '-egress'}

    def get(self, sid):
        self.names(sid)
        row = self.db.execute('SELECT * FROM sessions WHERE id=?', (sid,)).fetchone()
        if not row:
            raise WorkerError('session_not_found')
        return dict(row)

    def event(self, sid, action, state):
        self.db.execute('INSERT INTO events(session_id,action,state,at) VALUES(?,?,?,?)', (sid, action, state, time.time()))
        self.db.commit()

    def transition(self, sid, state, failure=None):
        if failure is None:
            failure = self.get(sid)['failure']
        column = ',ready=?' if state == 'ready' else ',stopped=?' if state in ('stopped', 'failed') else ''
        values = [state, failure] + ([time.time()] if column else []) + [sid]
        self.db.execute(f'UPDATE sessions SET state=?,failure=?{column} WHERE id=?', values)
        self.event(sid, 'state_change', state)

    def ensure_owned(self, obj, sid=None):
        if obj is None:
            raise WorkerError('resource_missing')
        labels = obj.get('Labels') or obj.get('Config', {}).get('Labels') or {}
        if labels.get('poc.worker') != self.namespace or (sid and labels.get('poc.session') != sid):
            raise WorkerError('resource_ownership_mismatch')

    def cleanup(self, sid):
        names = self.names(sid)
        for key in ('agent', 'gateway'):
            obj = self.exists('container', names[key])
            if obj:
                self.ensure_owned(obj, sid)
                self.docker('rm', '-f', names[key])
        for key in ('internal', 'egress'):
            obj = self.exists('network', names[key])
            if obj:
                self.ensure_owned(obj, sid)
                self.docker('network', 'rm', names[key])
        shutil.rmtree(self.root / sid, ignore_errors=True)

    def stop(self, sid, reason='operator'):
        if self.get(sid)['state'] == 'stopped':
            self.cleanup(sid)
            return self.public(self.get(sid))
        self.db.execute('UPDATE sessions SET stop_reason=? WHERE id=?', (reason, sid))
        self.transition(sid, 'stopping')
        try:
            self.cleanup(sid)
        except WorkerError:
            self.event(sid, 'cleanup_incomplete', 'stopping')
            raise
        self.transition(sid, 'stopped')
        return self.public(self.get(sid))

    def reconcile(self):
        rows = self.db.execute("SELECT * FROM sessions WHERE state IN ('provisioning','stopping','ready')").fetchall()
        for row in rows:
            sid = row['id']
            if row['state'] in ('provisioning', 'stopping'):
                self.cleanup(sid)
                self.transition(sid, 'stopped' if row['state'] == 'stopping' else 'failed',
                                None if row['state'] == 'stopping' else 'interrupted_provisioning')
            else:
                if row['expires'] is not None and row['expires'] <= time.time():
                    self.event(sid, 'expiry_reached', row['state'])
                    self.stop(sid, reason='expired')
                    continue
                names = self.names(sid)
                agent = self.exists('container', names['agent'])
                gateway = self.exists('container', names['gateway'])
                if not all(obj and obj['State']['Running'] for obj in [agent, gateway]):
                    self.cleanup(sid)
                    self.transition(sid, 'failed', 'resource_lost')

    def public(self, row):
        return {key: row[key] for key in ('id', 'state', 'created', 'ready', 'stopped', 'failure', 'expires', 'stop_reason')} | {
            'owner': 'local-pilot', 'policy': 'codex-tls-pilot-v1', 'runtime': RUNTIME,
            'readiness': 'cli_and_gateway_ready_login_required' if row['state'] == 'ready' else 'not_ready',
            'workspace': 'shared-per-local-pilot'}

    def create(self, key):
        self.reconcile()
        request_key = hashlib.sha256(key.encode()).hexdigest()
        old = self.db.execute('SELECT * FROM sessions WHERE request_key=?', (request_key,)).fetchone()
        if old:
            return self.public(dict(old))
        if self.db.execute("SELECT COUNT(*) FROM sessions WHERE state='ready'").fetchone()[0] >= 5:
            raise WorkerError('quota_five_sessions')
        self.docker('image', 'inspect', AGENT)
        self.docker('image', 'inspect', GATEWAY)
        info = json.loads(self.docker('info', '--format', '{{json .Runtimes}}'))
        if RUNTIME not in info:
            raise WorkerError('runtime_unavailable')
        volume = self.exists('volume', self.volume)
        if volume:
            self.ensure_owned(volume)
        else:
            self.docker('volume', 'create', '--label', self.label, self.volume)
        sid = uuid.uuid4().hex
        created = time.time()
        self.db.execute('INSERT INTO sessions(id,request_key,state,created,expires) VALUES(?,?,?,?,?)',
                        (sid, request_key, 'provisioning', created, created + SESSION_LIFETIME_SECONDS))
        self.event(sid, 'create', 'provisioning')
        try:
            self.provision(sid)
            self.transition(sid, 'ready')
        except Exception:
            try:
                self.cleanup(sid)
                self.transition(sid, 'failed', 'provisioning_failed')
            except Exception:
                self.event(sid, 'cleanup_incomplete', 'provisioning')
            raise WorkerError('provisioning_failed') from None
        return self.public(self.get(sid))

    def provision(self, sid):
        names = self.names(sid)
        material = self.root / sid
        material.mkdir(mode=0o700)
        shutil.copyfile(ROOT / 'tls_gateway.py', material / 'addon.py')
        (material / 'addon.py').chmod(0o644)
        labels = ['--label', self.label, '--label', f'poc.session={sid}']
        for key in ('internal', 'egress'):
            self.docker('network', 'create', *labels, *(['--internal'] if key == 'internal' else []), names[key])
        self.docker('run', '-d', '--name', names['gateway'], *labels, '--network', names['egress'],
                    '--user', '10001:10001', '--read-only', '--tmpfs', '/tmp:size=64m,nosuid,nodev',
                    '--cpus=1', '--memory=512m', '--pids-limit=128', '--cap-drop=ALL', '--security-opt=no-new-privileges',
                    '-e', 'POC_ALLOWED_HOSTS=auth.openai.com,chatgpt.com,api.openai.com',
                    '-v', f'{material}/addon.py:/opt/addon.py:ro', '--entrypoint', 'mitmdump', GATEWAY,
                    '-q', '--listen-port', '3128', '--set', 'confdir=/tmp/ca', '--set', 'connection_strategy=lazy',
                    '--set', 'upstream_cert=false', '--set', 'rawtcp=false', '--set', 'http2=false',
                    '--set', 'ssl_insecure=false', '--set', 'validate_inbound_headers=true', '-s', '/opt/addon.py')
        self.docker('network', 'connect', names['internal'], names['gateway'])
        for _ in range(40):
            try:
                cert = self.docker('exec', names['gateway'], 'cat', '/tmp/ca/mitmproxy-ca-cert.pem')
                self.docker('exec', names['gateway'], 'python3', '-c',
                            'import socket;s=socket.create_connection(("127.0.0.1",3128),timeout=1);s.close()')
                break
            except WorkerError:
                time.sleep(0.25)
        else:
            raise WorkerError('gateway_not_ready')
        (material / 'ca.pem').write_text(cert + '\n')
        (material / 'ca.pem').chmod(0o644)
        gateway = self.exists('container', names['gateway'])
        ip = gateway['NetworkSettings']['Networks'][names['internal']]['IPAddress']
        env = []
        for var in ('HTTPS_PROXY', 'HTTP_PROXY', 'https_proxy', 'http_proxy'):
            env.extend(['-e', f'{var}=http://{ip}:3128'])
        for value in ('CODEX_CA_CERTIFICATE=/trust/ca.pem', 'SSL_CERT_FILE=/trust/ca.pem',
                      'NODE_EXTRA_CA_CERTS=/trust/ca.pem', 'NO_PROXY=localhost,127.0.0.1,::1',
                      'DISABLE_UPDATES=1', 'DISABLE_AUTOUPDATER=1'):
            env.extend(['-e', value])
        self.docker('run', '-d', '--name', names['agent'], *labels, '--log-driver=none',
                    '--runtime', RUNTIME, '--network', names['internal'], '--user', '10001:10001',
                    '--read-only', '--cpus=1', '--memory=1g', '--pids-limit=128',
                    '--cap-drop=ALL', '--security-opt=no-new-privileges',
                    '--tmpfs', '/tmp:size=256m,uid=10001,gid=10001,nosuid,nodev',
                    '--tmpfs', '/home/agent:size=512m,uid=10001,gid=10001,nosuid,nodev',
                    '--mount', f'type=volume,source={self.volume},target=/workspace',
                    '-v', f'{material}/ca.pem:/trust/ca.pem:ro', *env, AGENT, 'sleep', 'infinity')
        self.docker('exec', '-i', names['agent'], 'sh', '-c',
                    'umask 077; mkdir -p "$HOME/.codex"; cat > "$HOME/.codex/config.toml"', input=CONFIG)
        self.docker('exec', names['agent'], 'sh', '-c', 'test -w /workspace && codex --version')

    def interactive(self, sid, login):
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            raise WorkerError('interactive_terminal_required')
        with self.locked():
            self.reconcile()
            if self.get(sid)['state'] != 'ready':
                raise WorkerError('session_not_ready')
            obj = self.exists('container', self.names(sid)['agent'])
            self.ensure_owned(obj, sid)
            self.event(sid, 'login_requested' if login else 'attach_requested', 'ready')
        cmd = ['docker', 'exec', '-it', self.names(sid)['agent'], 'codex', '--no-daemon']
        cmd += ['login', '--device-auth'] if login else ['--sandbox', 'workspace-write', '--ask-for-approval', 'on-request']
        return subprocess.call(cmd)

    def health(self):
        result = {'active': False, 'stale': True, 'interval_seconds': 30,
                  'last_attempt': None, 'last_success': None, 'error': 'health_unavailable'}
        try:
            data = json.loads((self.root / 'reconciler-health.json').read_text())
            for key in ('last_attempt', 'last_success', 'interval_seconds'):
                if data.get(key) is not None and not isinstance(data[key], (int, float)):
                    raise ValueError()
                result[key] = data.get(key)
            result['error'] = None if data.get('error') is None else 'worker_unavailable_or_cleanup_failed'
            result['stale'] = not result['last_attempt'] or time.time() - result['last_attempt'] > max(90, 3 * (result['interval_seconds'] or 30))
            default = pathlib.Path('~/.local/state/gvisor-poc-worker').expanduser().resolve()
            if self.root == default:
                status = subprocess.run(['systemctl', '--user', 'is-active', 'gvisor-poc-reconciler.service'], capture_output=True, text=True, timeout=5)
                result['active'] = status.returncode == 0 and status.stdout.strip() == 'active'
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', default='~/.local/state/gvisor-poc-worker')
    parser.add_argument('action', choices=['create', 'list', 'inspect', 'stop', 'reconcile', 'health', 'monitor', 'collect-security', 'security-events', 'alerts', 'acknowledge-alert', 'resolve-alert', 'login', 'attach', 'events'])
    parser.add_argument('id', nargs='?')
    parser.add_argument('--key', default=None)
    parser.add_argument('--before', type=int)
    parser.add_argument('--kind', choices=['lifecycle', 'lifecycle_failure', 'egress_denied', 'policy_drift'])
    args = parser.parse_args()
    try:
        worker = Worker(args.state_dir)
        if args.action == 'health':
            print(json.dumps(worker.health()))
            return
        if args.action == 'monitor':
            from console_observability import snapshot
            print(json.dumps(snapshot(worker)))
            return
        if args.action == 'collect-security':
            from security_history import collect
            print(json.dumps(collect(worker)))
            return
        if args.action in ('login', 'attach'):
            raise SystemExit(worker.interactive(args.id or '', args.action == 'login'))
        with worker.locked():
            if args.action in ('alerts', 'security-events', 'acknowledge-alert', 'resolve-alert'):
                from security_history import alerts, history, transition
                try:
                    result = alerts(worker) if args.action == 'alerts' else history(worker, args.before, args.kind) if args.action == 'security-events' else transition(worker, args.id or '', 'acknowledge' if args.action == 'acknowledge-alert' else 'resolve')
                except ValueError as exc:
                    raise WorkerError(str(exc)) from None
            elif args.action == 'create':
                result = worker.create(args.key or uuid.uuid4().hex)
            elif args.action == 'list':
                result = [worker.public(dict(r)) for r in worker.db.execute('SELECT * FROM sessions ORDER BY created')]
            elif args.action == 'inspect':
                result = worker.public(worker.get(args.id or ''))
            elif args.action == 'stop':
                result = worker.stop(args.id or '')
            elif args.action == 'events':
                worker.get(args.id or '')
                result = [dict(r) for r in worker.db.execute('SELECT sequence,action,state,at FROM events WHERE session_id=? ORDER BY sequence', (args.id,))]
            else:
                worker.reconcile()
                result = {'reconciled': True}
        print(json.dumps(result))
    except WorkerError as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Loopback-only, single-operator console. No remote/browser terminal execution."""
import argparse
import hmac
import json
import mimetypes
import pathlib
import re
import secrets
import shlex
import subprocess
import threading
import time
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

ROOT = pathlib.Path(__file__).resolve().parent.parent
POLICY = 'codex-tls-pilot-v1'


def recorded_timings():
    try:
        data = json.loads((ROOT / 'results/coding-task-20261113/summary.json').read_text())
        fields = {'First response': 'first_response_seconds', 'First tool': 'first_tool_seconds', 'Completion': 'process_completed_seconds'}
        result = []
        for label, key in fields.items():
            value = data[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 3600:
                return []
            result.append({'label': label, 'seconds': value})
        return result
    except (OSError, ValueError, KeyError, TypeError):
        return []


class Adapter:
    def __init__(self, state=None):
        self.state = state
        home = subprocess.check_output(['limactl', 'shell', 'gvisor-poc', '--', 'printenv', 'HOME'], text=True, timeout=20).strip()
        if not home.startswith('/') or '\n' in home:
            raise RuntimeError('invalid_guest_home')
        self.command = ['limactl', 'shell', 'gvisor-poc', '--', 'python3', home + '/gvisor-managed-pilot/scripts/manage_codex_session.py']
        if state:
            self.command.extend(['--state-dir', state])

    def run(self, *args):
        p = subprocess.run([*self.command, *args], text=True, capture_output=True, timeout=120)
        if p.returncode:
            try:
                code = json.loads(p.stderr)['error']
            except (ValueError, KeyError, TypeError):
                code = 'worker_unavailable'
            if not re.fullmatch('[a-z_]+', code):
                code = 'worker_failed'
            raise RuntimeError(code)
        return json.loads(p.stdout)


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, adapter, sweep_seconds=30):
        super().__init__(address, Handler)
        self.adapter = adapter
        self.secret = secrets.token_urlsafe(32)
        self.origin = f'http://127.0.0.1:{self.server_port}'
        self.sweep_seconds = sweep_seconds
        self.cleanup_status = {'interval_seconds': sweep_seconds, 'last_attempt': None, 'last_success': None, 'error': None}
        self.stop_sweeper = threading.Event()
        self.sweeper = threading.Thread(target=self.sweep, daemon=True)
        self.sweeper.start()

    def sweep(self):
        while not self.stop_sweeper.wait(self.sweep_seconds):
            self.cleanup_status['last_attempt'] = time.time()
            try:
                self.adapter.run('reconcile')
                self.cleanup_status.update(last_success=time.time(), error=None)
            except Exception:
                self.cleanup_status['error'] = 'worker_unavailable'

    def server_close(self):
        if hasattr(self, 'stop_sweeper'):
            self.stop_sweeper.set()
            self.sweeper.join(timeout=1)
        super().server_close()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass  # Never log cookies, request headers, or bodies.

    def reply(self, status, value, cookie=False):
        data = json.dumps(value).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(data)))
        if cookie:
            self.send_header('Set-Cookie', f'poc_console={self.server.secret}; HttpOnly; SameSite=Strict; Path=/')
        self.end_headers()
        self.wfile.write(data)

    def boundary(self, authenticated=False):
        if len(self.headers.get_all('Host', [])) != 1 or len(self.headers.get_all('Origin', [])) > 1:
            return False
        if self.client_address[0] != '127.0.0.1' or self.headers.get('Host') != self.server.origin.removeprefix('http://'):
            return False
        if self.headers.get('Origin') not in (None, self.server.origin):
            return False
        if self.headers.get('Sec-Fetch-Site') not in (None, 'none', 'same-origin'):
            return False
        if authenticated:
            try:
                cookie = SimpleCookie(self.headers.get('Cookie', ''))
                value = cookie['poc_console'].value
            except (KeyError, ValueError, CookieError):
                return False
            if not hmac.compare_digest(value, self.server.secret):
                return False
        return True

    def do_GET(self):
        if not self.boundary():
            return self.reply(403, {'error': 'local_origin_required'})
        path = urlsplit(self.path).path
        if path == '/api/bootstrap':
            return self.reply(200, {'csrf': self.server.secret}, cookie=True)
        if path.startswith('/api/'):
            if not self.boundary(True):
                return self.reply(401, {'error': 'local_session_required'})
            return self.api(path, None)
        assets = {'/': ROOT / 'ui/console/index.html', '/app.js': ROOT / 'ui/console/app.js',
                  '/styles.css': ROOT / 'ui/prototype/styles.css', '/console.css': ROOT / 'ui/console/console.css'}
        target = assets.get(path)
        if path.startswith('/docs/'):
            candidate = (ROOT / unquote(path).lstrip('/')).resolve()
            if candidate.is_relative_to(ROOT / 'docs') and candidate.suffix in ('.md', '.svg'):
                target = candidate
        if not target or not target.is_file():
            return self.reply(404, {'error': 'not_found'})
        data = target.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', mimetypes.guess_type(str(target))[0] or 'text/plain')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if not self.boundary(True) or not hmac.compare_digest(self.headers.get('X-POC-CSRF', ''), self.server.secret):
            return self.reply(403, {'error': 'request_not_authorized'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if (len(self.headers.get_all('Content-Length', [])) != 1 or self.headers.get('Transfer-Encoding')
                    or not 0 < size <= 4096 or self.headers.get('Content-Type') != 'application/json'):
                raise ValueError()
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError()
        except (ValueError, UnicodeDecodeError):
            return self.reply(400, {'error': 'invalid_json_request'})
        return self.api(urlsplit(self.path).path, body)

    def api(self, path, body):
        try:
            if path == '/api/alerts' and body is None:
                return self.reply(200, self.server.adapter.run('alerts'))
            if path == '/api/security-events' and body is None:
                query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
                if set(query) - {'before', 'kind'} or any(len(v) != 1 for v in query.values()):
                    return self.reply(400, {'error': 'invalid_history_query'})
                args = ['security-events']
                if 'before' in query:
                    if not re.fullmatch(r'[1-9][0-9]{0,17}', query['before'][0]):
                        return self.reply(400, {'error': 'invalid_history_cursor'})
                    args.extend(['--before', query['before'][0]])
                if 'kind' in query:
                    if query['kind'][0] not in ('lifecycle', 'lifecycle_failure', 'egress_denied', 'policy_drift'):
                        return self.reply(400, {'error': 'invalid_history_kind'})
                    args.extend(['--kind', query['kind'][0]])
                return self.reply(200, self.server.adapter.run(*args))
            alert = re.fullmatch(r'/api/alerts/([a-f0-9]{32})/(acknowledge|resolve)', path)
            if alert:
                if body is None:
                    return self.reply(405, {'error': 'post_required'})
                if body:
                    return self.reply(400, {'error': 'invalid_alert_action'})
                aid, operation = alert.groups()
                return self.reply(200, self.server.adapter.run(operation + '-alert', aid))
            if path == '/api/monitor' and body is None:
                data = self.server.adapter.run('monitor')
                data['recorded_timings'] = recorded_timings()
                return self.reply(200, data)
            if path == '/api/sessions' and body is None:
                self.server.adapter.run('reconcile')
                return self.reply(200, {'sessions': self.server.adapter.run('list'), 'policy_id': POLICY,
                                        'quota': 5, 'runtime': 'runsc-stable-20261109',
                                        'cleanup': dict(self.server.cleanup_status),
                                        'resident_cleanup': self.server.adapter.run('health'), 'new_session_lifetime_seconds': 3600})
            if path == '/api/sessions' and body is not None:
                if set(body) != {'policy_id'} or body['policy_id'] != POLICY:
                    return self.reply(400, {'error': 'approved_policy_required'})
                key = self.headers.get('Idempotency-Key', '')
                if not re.fullmatch('[a-zA-Z0-9-]{8,64}', key):
                    return self.reply(400, {'error': 'idempotency_key_required'})
                return self.reply(201, self.server.adapter.run('create', '--key', key))
            match = re.fullmatch(r'/api/sessions/([a-f0-9]{32})(?:/(stop|events|terminal))?', path)
            if not match:
                return self.reply(404, {'error': 'not_found'})
            sid, action = match.groups()
            if body is not None:
                if action != 'stop' or body:
                    return self.reply(400, {'error': 'invalid_action'})
                return self.reply(200, self.server.adapter.run('stop', sid))
            if action == 'stop':
                return self.reply(405, {'error': 'post_required'})
            if action == 'terminal':
                row = self.server.adapter.run('inspect', sid)
                if row['state'] != 'ready':
                    return self.reply(409, {'error': 'session_not_ready'})
                base = 'limactl shell gvisor-poc -- bash -lc '
                def command(action):
                    inner = 'python3 "$HOME/gvisor-managed-pilot/scripts/manage_codex_session.py"'
                    if getattr(self.server.adapter, 'state', None):
                        inner += ' --state-dir ' + shlex.quote(self.server.adapter.state)
                    return base + shlex.quote(inner + ' ' + action + ' ' + sid)
                return self.reply(200, {'login': command('login'), 'attach': command('attach'), 'mode': 'private_mac_terminal'})
            return self.reply(200, self.server.adapter.run('events' if action == 'events' else 'inspect', sid))
        except (RuntimeError, subprocess.SubprocessError, OSError, ValueError) as exc:
            code = str(exc) if isinstance(exc, RuntimeError) else 'worker_unavailable'
            status = 409 if code in ('quota_five_sessions', 'alert_already_resolved') else 404 if code in ('session_not_found', 'alert_not_found') else 503
            return self.reply(status, {'error': code})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=4180)
    parser.add_argument('--state-dir', help='Operator-only guest state path for isolated tests')
    args = parser.parse_args()
    server = Server(('127.0.0.1', args.port), Adapter(args.state_dir))
    print(f'Local console: {server.origin}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

#!/usr/bin/env python3
"""Loopback console with personal-mode PTY terminal and optional OIDC identity."""
import argparse
import base64
import hmac
import json
import mimetypes
import pathlib
import re
import secrets
import shlex
import signal
import subprocess
import sys
import threading
import time
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from console_auth import AuthConfigurationError, load_profile
from console_oidc import BrowserAuth, LoginError
from terminal_relay import TerminalRelay, TerminalError

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
    def __init__(self, state=None, principal="local-pilot", role="operator"):
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}",principal) or role not in ("member","operator"):
            raise ValueError("invalid_principal")
        self.state, self.principal, self.role = state, principal, role
        home = subprocess.check_output(['limactl', 'shell', 'gvisor-poc', '--', 'printenv', 'HOME'], text=True, timeout=20).strip()
        if not home.startswith('/') or '\n' in home:
            raise RuntimeError('invalid_guest_home')
        self.command = ['limactl', 'shell', 'gvisor-poc', '--', 'python3', home + '/gvisor-managed-pilot/scripts/manage_codex_session.py']
        self.command.extend(['--principal',principal,'--role',role])
        if state:
            self.command.extend(['--state-dir', state])

    def for_identity(self, principal, role):
        # New immutable command binding per request. Never mutate the shared operator adapter.
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", principal) or role not in ('member', 'operator'):
            raise ValueError('invalid_principal')
        bound = object.__new__(type(self))
        bound.state, bound.principal, bound.role = self.state, principal, role
        bound.command = list(self.command)
        index = bound.command.index('--principal')
        bound.command[index + 1] = principal
        bound.command[bound.command.index('--role') + 1] = role
        return bound

    def terminal_command(self, sid, mode, terminal_id):
        if not re.fullmatch('[a-f0-9]{32}', sid) or not re.fullmatch('[a-f0-9]{32}', terminal_id) or mode not in ('login','attach'):
            raise ValueError('invalid_terminal_request')
        return [self.command[0], '--tty=true', *self.command[1:], mode, sid, '--terminal-id', terminal_id]

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

    def __init__(self, address, adapter, sweep_seconds=30, auth=None):
        super().__init__(address, Handler)
        self.adapter = adapter
        self.auth = auth
        self.terminals = TerminalRelay()
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
        if hasattr(self, "terminals"):
            self.terminals.close()
        super().server_close()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass  # Never log cookies, request headers, or bodies.

    def reply(self, status, value, cookie=False, clear_sso=False):
        data = json.dumps(value).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(data)))
        if cookie:
            if not self.cookie_value('poc_terminal_browser'):
                self.send_header('Set-Cookie', f'{self.cookie_name("poc_terminal_browser")}={secrets.token_urlsafe(32)}; HttpOnly; SameSite=Strict; Path=/')
            self.send_header('Set-Cookie', f'{self.cookie_name("poc_console")}={self.server.secret}; HttpOnly; SameSite=Strict; Path=/')
        if clear_sso:
            self.send_header('Set-Cookie', f'{self.cookie_name("poc_sso")}=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0')
        self.end_headers()
        self.wfile.write(data)

    def cookie_name(self, name):
        return f"{name}_{self.server.server_port}"

    def cookie_value(self, name):
        try:
            if len(self.headers.get_all('Cookie', [])) > 1:
                return ''
            cookies = SimpleCookie(self.headers.get('Cookie', ''))
            value = cookies[self.cookie_name(name)].value
            return value if re.fullmatch(r'[A-Za-z0-9_-]{43}', value) else ''
        except (KeyError, ValueError, CookieError):
            return ''

    def redirect(self, location, cookies=()):
        self.send_response(303)
        self.send_header('Location', location)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Length', '0')
        for cookie in cookies:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()

    def boundary(self, authenticated=False, callback=False):
        if len(self.headers.get_all('Host', [])) != 1 or len(self.headers.get_all('Origin', [])) > 1:
            return False
        if self.client_address[0] != '127.0.0.1' or self.headers.get('Host') != self.server.origin.removeprefix('http://'):
            return False
        if self.headers.get('Origin') not in (None, self.server.origin):
            return False
        site = self.headers.get('Sec-Fetch-Site')
        if site not in (None, 'none', 'same-origin'):
            if not (callback and site == 'cross-site' and self.headers.get('Sec-Fetch-Mode') == 'navigate'
                    and self.headers.get('Sec-Fetch-Dest') == 'document'):
                return False
        if authenticated:
            if self.server.auth:
                try:
                    self.identity = self.server.auth.authenticate(self.cookie_value('poc_sso'))
                    self.csrf = self.identity['csrf']
                    self.adapter = self.server.adapter.for_identity(self.identity['principal'], self.identity['role'])
                except LoginError:
                    return False
            else:
                if not hmac.compare_digest(self.cookie_value('poc_console'), self.server.secret):
                    return False
                self.adapter, self.csrf = self.server.adapter, self.server.secret
        return True

    def do_GET(self):
        path = urlsplit(self.path).path
        if not self.boundary(callback=bool(self.server.auth and path == '/auth/callback')):
            return self.reply(403, {'error': 'local_origin_required'})
        if self.server.auth and path in ('/auth/login', '/auth/callback'):
            try:
                if path == '/auth/login':
                    browser, location = self.server.auth.begin(self.cookie_value('poc_oidc_tx'))
                    return self.redirect(location, [f'{self.cookie_name("poc_oidc_tx")}={browser}; HttpOnly; SameSite=Lax; Path=/auth; Max-Age=300'])
                if len(self.path) > 8192:
                    raise LoginError('sso_transaction_invalid')
                query = parse_qs(urlsplit(self.path).query, keep_blank_values=True, max_num_fields=8)
                if any(len(values) != 1 for values in query.values()):
                    raise LoginError('sso_transaction_invalid')
                sid = self.server.auth.finish(self.cookie_value('poc_oidc_tx'),
                    {key: values[0] for key, values in query.items()}, self.cookie_value('poc_sso'))
                return self.redirect('/', [f'{self.cookie_name("poc_oidc_tx")}=; HttpOnly; SameSite=Lax; Path=/auth; Max-Age=0',
                    f'{self.cookie_name("poc_sso")}={sid}; HttpOnly; SameSite=Lax; Path=/; Max-Age=3600'])
            except (LoginError, ValueError):
                # No callback parameters, provider errors or credentials appear in response/logs.
                return self.redirect('/login?failed=1', [f'{self.cookie_name("poc_oidc_tx")}=; HttpOnly; SameSite=Lax; Path=/auth; Max-Age=0'])
        if path == '/api/bootstrap':
            if self.server.auth:
                if not self.boundary(True):
                    return self.reply(401, {'error': 'sso_session_required'})
                return self.reply(200, {'csrf': self.csrf})
            return self.reply(200, {'csrf': self.server.secret}, cookie=True)
        if path.startswith('/api/'):
            if not self.boundary(True):
                return self.reply(401, {'error': 'sso_session_required' if self.server.auth else 'local_session_required'})
            return self.api(path, None)
        assets = {'/': ROOT / 'ui/console/index.html', '/app.js': ROOT / 'ui/console/app.js',
                  '/styles.css': ROOT / 'ui/prototype/styles.css', '/console.css': ROOT / 'ui/console/console.css',
                  '/terminal.html': ROOT / 'ui/console/terminal.html', '/terminal.js': ROOT / 'ui/console/terminal.js'}
        for name in ('xterm.js','xterm.css','addon-fit.js'):
            assets['/vendor/'+name] = ROOT / 'ui/console/vendor' / name
        if self.server.auth:
            assets['/login'] = ROOT / 'ui/console/login.html'
            if path not in ('/login', '/console.css', '/styles.css') and not self.boundary(True):
                return self.redirect('/login')
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
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Frame-Options', 'SAMEORIGIN' if path == '/terminal.html' else 'DENY')
        self.send_header('X-Content-Type-Options', 'nosniff')
        # xterm creates renderer style elements; allow those only on the terminal page.
        style = "'self' 'unsafe-inline'" if path == '/terminal.html' else "'self'"
        ancestors = "'self'" if path == '/terminal.html' else "'none'"
        self.send_header('Content-Security-Policy', f"default-src 'self'; script-src 'self'; style-src {style}; connect-src 'self'; frame-src 'self'; frame-ancestors {ancestors}; base-uri 'none'; form-action 'self'; object-src 'none'")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if not self.boundary(True) or not hmac.compare_digest(self.headers.get('X-POC-CSRF', '').encode(), self.csrf.encode()):
            return self.reply(403, {'error': 'request_not_authorized'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if (len(self.headers.get_all('Content-Length', [])) != 1 or self.headers.get('Transfer-Encoding')
                    or not 0 < size <= 8192 or self.headers.get('Content-Type') != 'application/json'):
                raise ValueError()
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError()
        except (ValueError, UnicodeDecodeError):
            return self.reply(400, {'error': 'invalid_json_request'})
        if self.server.auth and urlsplit(self.path).path == '/auth/logout':
            if body:
                return self.reply(400, {'error': 'invalid_logout_request'})
            self.server.auth.logout(self.cookie_value('poc_sso'))
            return self.reply(200, {'logged_out': True}, clear_sso=True)
        return self.api(urlsplit(self.path).path, body)

    def api(self, path, body):
        try:
            if path in ('/api/workspace/deletion-prepare', '/api/workspace/delete'):
                if body is None:
                    return self.reply(405, {'error': 'post_required'})
                if urlsplit(self.path).query:
                    return self.reply(400, {'error': 'invalid_workspace_deletion'})
                if path.endswith('deletion-prepare'):
                    if body:
                        return self.reply(400, {'error': 'invalid_workspace_deletion'})
                    return self.reply(200, self.adapter.run('prepare-workspace-deletion'))
                if (set(body) != {'token','confirmation'} or not isinstance(body['token'],str)
                        or not re.fullmatch('[a-f0-9]{64}',body['token'])
                        or body['confirmation'] != 'DELETE WORKSPACE'):
                    return self.reply(400, {'error': 'invalid_workspace_deletion'})
                return self.reply(200, self.adapter.run('delete-workspace', '--confirmation-token', body['token'], '--confirmation', body['confirmation']))
            if path == '/api/workspace/export':
                if body is None:
                    return self.reply(405, {'error': 'post_required'})
                if body or urlsplit(self.path).query:
                    return self.reply(400, {'error': 'invalid_workspace_export'})
                from workspace_export import MAX_ARCHIVE_BYTES
                encoded = self.adapter.run('export-workspace')['archive_base64']
                if not isinstance(encoded, str) or len(encoded) > 4*((MAX_ARCHIVE_BYTES+2)//3):
                    raise RuntimeError('workspace_export_invalid')
                data = base64.b64decode(encoded, validate=True)
                if not data or len(data) > MAX_ARCHIVE_BYTES:
                    raise RuntimeError('workspace_export_invalid')
                self.send_response(200)
                self.send_header('Content-Type', 'application/x-tar')
                self.send_header('Content-Disposition', 'attachment; filename="workspace.tar"')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            if path == '/api/workspace':
                if body is not None:
                    return self.reply(405, {'error': 'get_required'})
                if urlsplit(self.path).query:
                    return self.reply(400, {'error': 'invalid_workspace_query'})
                return self.reply(200, self.adapter.run('workspace'))
            terminal_ticket = re.fullmatch(r'/api/sessions/([a-f0-9]{32})/terminal-ticket', path)
            terminal_route = re.fullmatch(r'/api/terminals/([A-Za-z0-9_-]{43})(?:/(input|resize|close))?', path)
            if terminal_ticket or terminal_route or path == '/api/terminals':
                if self.server.auth:
                    return self.reply(501, {'error': 'terminal_personal_pilot_only'})
                browser = self.cookie_value('poc_terminal_browser')
                if terminal_ticket:
                    if body is None:
                        return self.reply(405, {'error': 'post_required'})
                    if set(body) != {'mode'}:
                        return self.reply(400, {'error': 'invalid_terminal_request'})
                    return self.reply(201, self.server.terminals.issue(self.adapter, browser, terminal_ticket[1], body['mode']))
                if path == '/api/terminals':
                    if body is None:
                        return self.reply(405, {'error': 'post_required'})
                    if set(body) != {'ticket','cols','rows'}:
                        return self.reply(400, {'error': 'invalid_terminal_request'})
                    return self.reply(201, self.server.terminals.connect(self.adapter, browser, body['ticket'], body['cols'], body['rows']))
                channel = self.server.terminals.get(self.adapter, browser, terminal_route[1])
                operation = terminal_route[2]
                if operation is None and body is None:
                    query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
                    if set(query) != {'cursor'} or len(query['cursor']) != 1 or not re.fullmatch('[0-9]{1,12}', query['cursor'][0]):
                        return self.reply(400, {'error': 'invalid_terminal_cursor'})
                    return self.reply(200, channel.output(int(query['cursor'][0])))
                if body is None:
                    return self.reply(405, {'error': 'post_required'})
                if operation == 'input' and set(body) == {'data'}:
                    channel.input(body['data'])
                elif operation == 'resize' and set(body) == {'cols','rows'}:
                    channel.resize(body['cols'], body['rows'])
                elif operation == 'close' and not body:
                    channel.close()
                else:
                    return self.reply(400, {'error': 'invalid_terminal_request'})
                return self.reply(200, {'accepted': True})
            if path == '/api/identity' and body is None:
                return self.reply(200, {'principal':getattr(self.adapter,'principal','local-pilot'), 'role':getattr(self.adapter,'role','operator'), 'mode':'okta_oidc' if self.server.auth else 'server_bound_local_operator', 'organization_sso':bool(self.server.auth)})
            if path == '/api/alert-rules' and body is None:
                return self.reply(200, self.adapter.run('alert-rules'))
            if path == '/api/alerts' and body is None:
                return self.reply(200, self.adapter.run('alerts'))
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
                    if query['kind'][0] not in ('lifecycle', 'lifecycle_failure', 'egress_denied', 'policy_drift', 'egress_burst', 'resource_pressure', 'sample_unavailable', 'collector_gap'):
                        return self.reply(400, {'error': 'invalid_history_kind'})
                    args.extend(['--kind', query['kind'][0]])
                return self.reply(200, self.adapter.run(*args))
            alert = re.fullmatch(r'/api/alerts/([a-f0-9]{32})/(acknowledge|resolve)', path)
            if alert:
                if body is None:
                    return self.reply(405, {'error': 'post_required'})
                if body:
                    return self.reply(400, {'error': 'invalid_alert_action'})
                aid, operation = alert.groups()
                return self.reply(200, self.adapter.run(operation + '-alert', aid))
            if path == '/api/monitor' and body is None:
                data = self.adapter.run('monitor')
                data['recorded_timings'] = recorded_timings()
                return self.reply(200, data)
            if path == '/api/sessions' and body is None:
                self.adapter.run('reconcile')
                return self.reply(200, {'sessions': self.adapter.run('list'), 'policy_id': POLICY,
                                        'quota': 2 if getattr(self.adapter,'role','operator')=='member' else 5, 'global_quota':5, 'runtime': 'runsc-stable-20261109',
                                        'cleanup': dict(self.server.cleanup_status),
                                        'resident_cleanup': self.adapter.run('health'), 'new_session_lifetime_seconds': 3600})
            if path == '/api/sessions' and body is not None:
                if set(body) != {'policy_id'} or body['policy_id'] != POLICY:
                    return self.reply(400, {'error': 'approved_policy_required'})
                key = self.headers.get('Idempotency-Key', '')
                if not re.fullmatch('[a-zA-Z0-9-]{8,64}', key):
                    return self.reply(400, {'error': 'idempotency_key_required'})
                return self.reply(201, self.adapter.run('create', '--key', key))
            match = re.fullmatch(r'/api/sessions/([a-f0-9]{32})(?:/(stop|events|terminal))?', path)
            if not match:
                return self.reply(404, {'error': 'not_found'})
            sid, action = match.groups()
            if body is not None:
                if action != 'stop' or body:
                    return self.reply(400, {'error': 'invalid_action'})
                result = self.adapter.run('stop', sid)
                self.server.terminals.revoke_session(sid)
                return self.reply(200, result)
            if action == 'stop':
                return self.reply(405, {'error': 'post_required'})
            if action == 'terminal':
                if self.server.auth:
                    return self.reply(501, {'error': 'secure_attach_relay_required'})
                row = self.adapter.run('authorize-attach', sid)
                if row['state'] != 'ready':
                    return self.reply(409, {'error': 'session_not_ready'})
                base = 'limactl shell gvisor-poc -- bash -lc '
                def command(action):
                    inner = 'python3 "$HOME/gvisor-managed-pilot/scripts/manage_codex_session.py"'
                    inner += ' --principal '+shlex.quote(getattr(self.adapter,'principal','local-pilot'))+' --role '+shlex.quote(getattr(self.adapter,'role','operator'))
                    if getattr(self.adapter, 'state', None):
                        inner += ' --state-dir ' + shlex.quote(self.adapter.state)
                    return base + shlex.quote(inner + ' ' + action + ' ' + sid)
                return self.reply(200, {'login': command('login'), 'attach': command('attach'), 'mode': 'private_mac_terminal'})
            return self.reply(200, self.adapter.run('events' if action == 'events' else 'inspect', sid))
        except TerminalError as exc:
            code = str(exc)
            status = 404 if code == 'terminal_not_found' else 403 if code == 'attach_owner_required' else 409 if code in ('terminal_capacity','session_not_ready','terminal_closed','terminal_output_unavailable','terminal_input_busy') else 400
            return self.reply(status, {'error': code})
        except (RuntimeError, subprocess.SubprocessError, OSError, ValueError) as exc:
            code = str(exc) if isinstance(exc, RuntimeError) else 'worker_unavailable'
            status = 403 if code in ('attach_owner_required','operator_required') else 409 if code in ('quota_five_sessions', 'quota_member_sessions', 'alert_already_resolved', 'workspace_in_use', 'workspace_confirmation_invalid', 'workspace_changed') else 404 if code in ('session_not_found', 'alert_not_found', 'workspace_not_found') else 503
            return self.reply(status, {'error': code})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=4180)
    parser.add_argument('--state-dir', help='Operator-only guest state path for isolated tests')
    parser.add_argument('--principal', help='Trusted operator-selected local principal; not SSO or end-user login')
    parser.add_argument('--role', choices=['member','operator'], help='Trusted server binding; defaults to member for an explicit principal')
    parser.add_argument('--auth-mode', choices=['personal', 'okta'], default='personal', help='Personal is loopback-only; Okta requires configured issuer, client secret and optional dependencies')
    parser.add_argument('--auth-config', help='Public Okta application/assignment JSON; never put secrets here')
    parser.add_argument('--check-auth-config', action='store_true', help='Validate configuration without network, Lima or a listening socket; does not verify login')
    args = parser.parse_args()
    try:
        profile = load_profile(args.auth_mode, args.auth_config, args.principal, args.role, args.port)
        if args.check_auth_config:
            print(json.dumps(profile.report()))
            return 0
        provider = profile.require_runnable()
    except AuthConfigurationError as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr)
        return 2
    auth = None
    if profile.mode == 'okta':
        auth = BrowserAuth(profile, provider, lambda: load_profile('okta', args.auth_config, port=args.port))
        # The trusted operator adapter is for reconciliation only, never an end-user fallback.
        adapter = Adapter(args.state_dir)
    else:
        adapter = Adapter(args.state_dir, profile.principal, profile.role)
    server = Server(('127.0.0.1', args.port), adapter, auth=auth)
    print(f'Local console: {server.origin}', flush=True)
    def terminate(_signum, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, terminate)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())

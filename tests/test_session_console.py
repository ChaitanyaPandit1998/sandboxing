import hashlib
import http.client
import importlib.util
import json
import os
import pathlib
import subprocess
import threading
import time
import unittest
import uuid

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('console', ROOT / 'scripts/serve_session_console.py')
console = importlib.util.module_from_spec(spec)
spec.loader.exec_module(console)
SID = 'a' * 32


class FakeAdapter:
    def __init__(self):
        self.reconciles = 0
        self.calls = []

    def run(self, action, *args):
        self.calls.append((action, args))
        if action == 'reconcile':
            self.reconciles += 1
        row = {'id': SID, 'state': 'ready', 'runtime': 'runsc-stable-20261109', 'created': 1}
        return {'health': {'active': True, 'stale': False, 'last_success': 1, 'error': None},
                'monitor': {'sampled_at': 1, 'allowed_hosts': ['auth.openai.com'], 'sessions': [], 'signals': []},
                'alerts': {'alerts': [], 'counts': {'open':0,'acknowledged':0,'resolved':0},'last_collection':None,'collection_errors':0,'audit':[]},
                'security-events': {'events': [], 'next_before':None,'retention_days':30,'max_events':10000},
                'acknowledge-alert': {'id': SID, 'status':'acknowledged'}, 'resolve-alert': {'id': SID, 'status':'resolved'},
                'reconcile': {}, 'list': [row], 'create': row, 'stop': row,
                'inspect': row, 'events': [{'sequence': 1, 'action': 'create', 'state': 'ready', 'at': 1}]}[action]


class ConsoleTests(unittest.TestCase):
    def setUp(self):
        self.server = console.Server(('127.0.0.1', 0), FakeAdapter())
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.cookie = None
        self.csrf = None

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, path, method='GET', body=None, headers=None):
        values = dict(headers or {})
        if self.cookie:
            values.setdefault('Cookie', self.cookie)
        if method == 'POST':
            values.setdefault('Content-Type', 'application/json')
            values.setdefault('Origin', self.server.origin)
            if self.csrf:
                values.setdefault('X-POC-CSRF', self.csrf)
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=120)
        conn.request(method, path, body=json.dumps(body) if body is not None else None, headers=values)
        response = conn.getresponse()
        data = response.read()
        status, response_headers = response.status, dict(response.getheaders())
        conn.close()
        return status, response_headers, data

    def bootstrap(self):
        status, headers, data = self.request('/api/bootstrap')
        self.assertEqual(status, 200)
        self.cookie = headers['Set-Cookie'].split(';')[0]
        self.csrf = json.loads(data)['csrf']
        return headers

    def test_authentication_required(self):
        self.assertEqual(self.request('/api/sessions')[0], 401)

    def test_cookie_is_private_and_no_store(self):
        headers = self.bootstrap()
        self.assertIn('HttpOnly', headers['Set-Cookie'])
        self.assertIn('SameSite=Strict', headers['Set-Cookie'])
        self.assertEqual(headers['Cache-Control'], 'no-store')

    def test_host_rebinding_denied(self):
        self.assertEqual(self.request('/api/bootstrap', headers={'Host': 'attacker.invalid'})[0], 403)

    def test_cross_origin_and_cross_site_denied(self):
        self.assertEqual(self.request('/api/bootstrap', headers={'Origin': 'https://attacker.invalid'})[0], 403)
        self.assertEqual(self.request('/api/bootstrap', headers={'Sec-Fetch-Site': 'cross-site'})[0], 403)

    def test_csrf_required(self):
        self.bootstrap()
        self.csrf = None
        self.assertEqual(self.request('/api/sessions', 'POST', {'policy_id': console.POLICY})[0], 403)

    def test_policy_tampering_rejected(self):
        self.bootstrap()
        self.assertEqual(self.request('/api/sessions', 'POST', {'policy_id': console.POLICY, 'image': 'unapproved'}, {'Idempotency-Key': 'test-key-123'})[0], 400)

    def test_create_requires_idempotency(self):
        self.bootstrap()
        self.assertEqual(self.request('/api/sessions', 'POST', {'policy_id': console.POLICY})[0], 400)

    def test_create_and_stop(self):
        self.bootstrap()
        self.assertEqual(self.request('/api/sessions', 'POST', {'policy_id': console.POLICY}, {'Idempotency-Key': 'test-key-123'})[0], 201)
        self.assertEqual(self.request(f'/api/sessions/{SID}/stop', 'POST', {})[0], 200)
        self.assertEqual(self.request(f'/api/sessions/{SID}/stop')[0], 405)

    def test_terminal_handoff_is_fixed(self):
        self.bootstrap()
        status, _, data = self.request(f'/api/sessions/{SID}/terminal')
        self.assertEqual(status, 200)
        self.assertIn('manage_codex_session.py', json.loads(data)['attach'])
        self.assertNotIn('docker exec', data.decode())

    def test_invalid_session_and_path_traversal(self):
        self.bootstrap()
        self.assertEqual(self.request('/api/sessions/not-an-id')[0], 404)
        self.assertEqual(self.request('/docs/%2e%2e/.git/config')[0], 404)

    def test_static_assets_and_frame_policy(self):
        status, headers, data = self.request('/')
        self.assertEqual(status, 200)
        self.assertEqual(headers['X-Frame-Options'], 'DENY')
        self.assertIn(b'REAL WORKER STATE', data)
        for path in ['/app.js', '/styles.css', '/console.css', '/docs/README.md']:
            self.assertEqual(self.request(path)[0], 200)

    def test_alert_actions_require_auth_csrf_and_fixed_body(self):
        self.assertEqual(self.request('/api/alerts')[0],401)
        self.assertEqual(self.request('/api/security-events')[0],401)
        self.bootstrap()
        self.assertEqual(self.request('/api/alerts')[0],200)
        for operation in ['acknowledge','resolve']:
            path = f'/api/alerts/{SID}/{operation}'
            self.assertEqual(self.request(path)[0],405)
            self.assertEqual(self.request(path,'POST',{}, {'X-POC-CSRF':'wrong'})[0],403)
            self.assertEqual(self.request(path,'POST',{'actor':'admin'})[0],400)
            self.assertEqual(self.request(path,'POST',{})[0],200)
        self.assertEqual(self.request('/api/alerts/not-id/resolve','POST',{})[0],404)

    def test_history_query_is_bounded_and_forwarded_as_arguments(self):
        self.bootstrap()
        self.assertEqual(self.request('/api/security-events?before=100&kind=egress_denied')[0],200)
        self.assertIn(('security-events',('--before','100','--kind','egress_denied')),self.server.adapter.calls)
        for query in ['before=-1','before=1%3Bwhoami','before=','before=1&before=2','kind=secret','limit=99999']:
            self.assertEqual(self.request('/api/security-events?'+query)[0],400)

    def test_monitor_requires_auth_and_is_read_only(self):
        self.assertEqual(self.request('/api/monitor')[0], 401)
        self.bootstrap()
        status, _, data = self.request('/api/monitor')
        self.assertEqual(status, 200)
        snapshot = json.loads(data)
        self.assertEqual(snapshot['sessions'], [])
        self.assertIn('recorded_timings', snapshot)
        self.assertEqual(self.request('/api/monitor', 'POST', {})[0], 404)

    def test_resident_health_is_returned(self):
        self.bootstrap()
        status, _, data = self.request('/api/sessions')
        self.assertEqual(status, 200)
        health = json.loads(data)['resident_cleanup']
        self.assertTrue(health['active'])
        self.assertFalse(health['stale'])
        self.assertIsNotNone(health['last_success'])

    def test_background_sweep_without_page_request(self):
        background = console.Server(('127.0.0.1', 0), FakeAdapter(), sweep_seconds=0.02)
        try:
            deadline = time.monotonic() + 2
            while background.cleanup_status['last_success'] is None and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertGreater(background.adapter.reconciles, 0)
            self.assertIsNotNone(background.cleanup_status['last_success'])
        finally:
            background.server_close()


@unittest.skipUnless(os.environ.get('POC_LIVE_CONSOLE') == '1', 'live Lima test explicitly enabled separately')
class LiveConsoleTests(unittest.TestCase):
    setUp = ConsoleTests.setUp
    tearDown = ConsoleTests.tearDown
    request = ConsoleTests.request
    bootstrap = ConsoleTests.bootstrap

    def test_live_worker_lifecycle(self):
        state = '/tmp/poc-console-api-test-' + uuid.uuid4().hex
        adapter = console.Adapter(state)
        self.server.adapter = adapter
        sid = None
        checks = {}
        try:
            self.bootstrap()
            create = lambda: self.request('/api/sessions', 'POST', {'policy_id': console.POLICY}, {'Idempotency-Key': 'live-api-create-123'})
            status, _, data = create(); self.assertEqual(status, 201)
            session = json.loads(data); sid = session['id']
            checks['created_login_ready'] = session['state'] == 'ready'
            checks['idempotent_create'] = json.loads(create()[2])['id'] == sid
            checks['listed'] = any(s['id'] == sid for s in json.loads(self.request('/api/sessions')[2])['sessions'])
            checks['inspect'] = json.loads(self.request(f'/api/sessions/{sid}')[2])['policy'] == console.POLICY
            checks['events'] = bool(json.loads(self.request(f'/api/sessions/{sid}/events')[2]))
            checks['terminal_handoff'] = sid in json.loads(self.request(f'/api/sessions/{sid}/terminal')[2])['login']
            # Inject an elapsed deadline; no one-hour wall-clock wait or active user data is involved.
            code = 'import sqlite3,sys,time; c=sqlite3.connect(sys.argv[1]+"/sessions.sqlite",timeout=30); c.execute("UPDATE sessions SET expires=? WHERE id=?",(time.time()-1,sys.argv[2])); c.commit()'
            subprocess.run(['limactl', 'shell', 'gvisor-poc', '--', 'python3', '-c', code, state, sid], check=True, capture_output=True)
            background = console.Server(('127.0.0.1', 0), adapter, sweep_seconds=0.1)
            try:
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    expired = json.loads(self.request(f'/api/sessions/{sid}')[2])
                    if expired['state'] == 'stopped' and background.cleanup_status['last_success'] is not None:
                        break
                    time.sleep(0.1)
                checks['background_expired_session'] = expired['state'] == 'stopped' and expired['stop_reason'] == 'expired'
                checks['background_sweep_recorded'] = background.cleanup_status['last_success'] is not None
            finally:
                background.server_close()
            checks['stopped'] = json.loads(self.request(f'/api/sessions/{sid}/stop', 'POST', {})[2])['state'] == 'stopped'
            checks['repeat_stop'] = json.loads(self.request(f'/api/sessions/{sid}/stop', 'POST', {})[2])['state'] == 'stopped'
            self.assertTrue(all(checks.values()), checks)
            print('LIVE_CHECKS ' + json.dumps(checks), flush=True)
        finally:
            if sid:
                adapter.run('stop', sid)
            namespace = hashlib.sha256(state.encode()).hexdigest()[:10]
            volume = f'poc-managed-{namespace}-pilot-workspace'
            command = ['limactl', 'shell', 'gvisor-poc', '--', 'docker']
            result = subprocess.run([*command, 'volume', 'inspect', volume], capture_output=True, text=True)
            if result.returncode == 0:
                self.assertEqual(json.loads(result.stdout)[0]['Labels']['poc.worker'], namespace)
                subprocess.run([*command, 'volume', 'rm', volume], capture_output=True, check=True)


if __name__ == '__main__':
    unittest.main()

import copy
import importlib.util
import json
import pathlib
import sqlite3
import unittest
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('observability', ROOT / 'scripts/console_observability.py')
monitor = importlib.util.module_from_spec(spec); spec.loader.exec_module(monitor)


class MonitoringTests(unittest.TestCase):
    def test_gateway_output_never_exposes_extra_fields_or_counts_nonpolicy_lines(self):
        lines = '\n'.join([json.dumps({'event': 'tls_policy', 'decision': 'deny', 'reason': 'connect_authority', 'authorization': 'PRIVATE', 'url': 'PRIVATE'}),
                           json.dumps({'event': 'tls_policy', 'decision': 'allow', 'reason': 'connect_tls_http_match'}),
                           json.dumps({'event': 'tls_policy', 'decision': 'deny', 'reason': 'PRIVATE'}),
                           '504 PRIVATE', 'null', '[]', '{malformed'])
        result = monitor.decisions(lines)
        self.assertEqual(result['counts'], {'allow': 1, 'deny': 1})
        self.assertNotIn('PRIVATE', json.dumps(result))
        self.assertEqual(result['deny_reasons'], {'connect_authority': 1})

    def test_unavailable_resources_remain_unknown_and_failures_are_only_review_signals(self):
        db = sqlite3.connect(':memory:'); db.row_factory = sqlite3.Row
        db.execute('CREATE TABLE sessions(id,state,created)')
        db.execute('CREATE TABLE events(sequence,session_id,action,state,at)')
        db.execute('INSERT INTO sessions VALUES(?,?,?)', ('a'*32, 'ready', 1))
        db.execute('INSERT INTO events VALUES(?,?,?,?,?)', (1, 'b'*32, 'state_change', 'failed', 1))
        def unavailable(*args):
            raise RuntimeError('private internal exception must not escape')
        worker = SimpleNamespace(db=db, names=lambda sid: {'agent':'a','gateway':'g','internal':'n'},
                                 exists=lambda *args: None, ensure_owned=unavailable)
        sample = monitor.snapshot(worker)
        self.assertEqual(sample['sessions'][0]['error'], 'sample_unavailable')
        self.assertEqual(sample['sessions'][0]['checks'], [])
        self.assertIsNone(sample['sessions'][0]['telemetry'])
        self.assertEqual(sample['signals'][0]['severity'], 'review')
        self.assertNotIn('private internal', json.dumps(sample))
        db.execute('DELETE FROM sessions')
        self.assertEqual(monitor.snapshot(worker)['sessions'], [])
        db.close()

    def test_persistent_deny_records_hash_only_known_flow_metadata(self):
        line=json.dumps({'event':'tls_policy','flow_id':'abcd1234-1234-1234-1234-123456789abc','decision':'deny','reason':'connect_authority','authorization':'PRIVATE'})
        rows=monitor.decision_records('a'*32,line+'\n'+line)
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0],rows[1])
        self.assertEqual(len(rows[0]['fingerprint']),64)
        self.assertNotIn('PRIVATE',json.dumps(rows))
        self.assertNotIn('abcd1234-',json.dumps(rows))
        self.assertEqual(monitor.decision_records('a'*32,line.replace('connect_authority','SECRET')),[])

    def fixtures(self):
        worker = SimpleNamespace(root=pathlib.Path('/private-state'), volume='owned-volume', names=lambda sid: {'internal': 'isolated-network'})
        agent = {'Config': {'User': '10001:10001'}, 'HostConfig': {'Runtime': 'runsc-stable-20261109', 'ReadonlyRootfs': True,
                  'SecurityOpt': ['no-new-privileges=true'], 'CapDrop': ['ALL'], 'CapAdd': [], 'Privileged': False,
                  'NanoCpus': 1000000000, 'Memory': 1073741824, 'PidsLimit': 128},
                 'NetworkSettings': {'Networks': {'isolated-network': {}}},
                 'Mounts': [{'Type': 'volume', 'Name': 'owned-volume', 'Destination': '/workspace'},
                            {'Type': 'bind', 'Source': '/private-state/session/ca.pem', 'Destination': '/trust/ca.pem', 'RW': False}]}
        gateway = {'Config': {'Env': ['POC_ALLOWED_HOSTS=auth.openai.com,chatgpt.com,api.openai.com']}}
        return worker, agent, gateway, {'Internal': True}

    def test_weakened_configurations_are_detected(self):
        w, agent, gateway, network = self.fixtures()
        self.assertTrue(all(c['status'] == 'pass' for c in monitor.policy_checks(w, 'session', agent, gateway, network)))
        mutations = [lambda a,g,n: a['HostConfig'].update(Privileged=True),
                     lambda a,g,n: a['HostConfig'].update(SecurityOpt=['no-new-privileges=false']),
                     lambda a,g,n: a['Mounts'].append({'Type':'bind','Source':'/','Destination':'/host','RW':False}),
                     lambda a,g,n: a['HostConfig'].update(Runtime='runc'),
                     lambda a,g,n: a['NetworkSettings']['Networks'].update({'external': {}}),
                     lambda a,g,n: g['Config'].update(Env=['POC_ALLOWED_HOSTS=example.com']),
                     lambda a,g,n: n.update(Internal=False)]
        for mutate in mutations:
            a,g,n = copy.deepcopy((agent,gateway,network)); mutate(a,g,n)
            self.assertTrue(any(c['status'] == 'fail' for c in monitor.policy_checks(w,'session',a,g,n)))


if __name__ == '__main__':
    unittest.main()

import contextlib
import importlib.util
import json
import pathlib
import sqlite3
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('history', ROOT / 'scripts/security_history.py')
history = importlib.util.module_from_spec(spec); spec.loader.exec_module(history)
SID = 'a' * 32


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = pathlib.Path(self.temp.name) / 'test.sqlite'
        self.open()
        self.db.executescript('CREATE TABLE IF NOT EXISTS events(sequence INTEGER PRIMARY KEY,session_id,action,state,at);')

    def open(self):
        self.db = sqlite3.connect(self.path); self.db.row_factory = sqlite3.Row
        history.initialize(self.db)
        self.worker = SimpleNamespace(db=self.db, locked=contextlib.nullcontext)

    def tearDown(self):
        self.db.close(); self.temp.cleanup()

    def sample(self, key='known-flow'):
        return {'_decision_records': [{'session_id': SID, 'fingerprint': history.digest(key)}], 'sessions': []}

    def test_dedup_ack_resolve_reopen_and_private_audit(self):
        history.ingest(self.worker, self.sample())
        alert = history.alerts(self.worker)['alerts'][0]
        history.transition(self.worker, alert['id'], 'acknowledge')
        history.transition(self.worker, alert['id'], 'acknowledge')
        history.ingest(self.worker, self.sample())
        current = history.alerts(self.worker)
        self.assertEqual(current['alerts'][0]['event_count'], 1)
        self.assertEqual(current['alerts'][0]['status'], 'acknowledged')
        history.transition(self.worker, alert['id'], 'resolve')
        history.ingest(self.worker, self.sample())
        self.assertEqual(history.alerts(self.worker)['alerts'][0]['status'], 'resolved')
        history.ingest(self.worker, self.sample('new-flow'))
        current = history.alerts(self.worker)
        self.assertEqual(current['alerts'][0]['status'], 'open')
        self.assertEqual(current['alerts'][0]['event_count'], 2)
        self.assertEqual([a['action'] for a in reversed(current['audit'])], ['opened','acknowledge','resolve','reopened'])
        self.assertTrue(all(a['actor'] in ('local-operator','collector') for a in current['audit']))

    def test_journal_and_alert_state_survive_db_reopen(self):
        history.ingest(self.worker, self.sample())
        aid = history.alerts(self.worker)['alerts'][0]['id']
        history.transition(self.worker, aid, 'acknowledge')
        self.db.close(); self.open()
        self.assertEqual(history.alerts(self.worker)['alerts'][0]['status'], 'acknowledged')
        self.assertEqual(len(history.history(self.worker)['events']), 1)

    def test_policy_drift_reopens_only_after_verified_recovery(self):
        sample = {'sessions': [{'id': SID, 'checks': [{'status':'fail'}]}]}
        history.ingest(self.worker, sample)
        aid = history.alerts(self.worker)['alerts'][0]['id']
        history.transition(self.worker, aid, 'resolve')
        history.ingest(self.worker, sample)
        history.ingest(self.worker, {'sessions':[{'id':SID, 'checks':[], 'error':'sample_unavailable'}]})
        self.assertEqual(history.alerts(self.worker)['alerts'][0]['status'], 'resolved')
        history.ingest(self.worker, {'sessions':[{'id':SID,'checks':[{'status':'pass'}]}]})
        history.ingest(self.worker, sample)
        self.assertEqual(history.alerts(self.worker)['alerts'][0]['status'], 'open')

    def test_lifecycle_cursor_and_unknown_values_do_not_leak(self):
        now = time.time()
        self.db.executemany('INSERT INTO events VALUES(?,?,?,?,?)', [(1,SID,'state_change','failed',now),(2,SID,'SECRET','SECRET',now),(3,SID,'login_requested','ready',now)])
        history.ingest(self.worker, {})
        history.ingest(self.worker, {})
        events = history.history(self.worker)['events']
        self.assertEqual(len(events), 2)
        self.assertEqual(history.alerts(self.worker)['counts']['open'], 1)
        self.assertNotIn('SECRET', json.dumps(events))

    def test_unresolved_alert_retained_and_resolved_retention_starts_on_resolution(self):
        now=time.time()
        history.record(self.db,'old-denial',SID,'egress_denied',history.DETAILS['egress_denied'],now-31*86400)
        self.db.commit();history.ingest(self.worker,{})
        alert=history.alerts(self.worker)['alerts'][0]
        self.assertEqual(alert['status'],'open')
        history.transition(self.worker,alert['id'],'resolve')
        history.ingest(self.worker,{})
        self.assertEqual(history.alerts(self.worker)['alerts'][0]['status'],'resolved')
        with patch.object(history.time,'time',return_value=now+31*86400):
            history.ingest(self.worker,{})
        self.assertEqual(history.alerts(self.worker)['alerts'],[])

    def test_pagination_filter_retention_and_invalid_actions(self):
        now = time.time()
        for i in range(105):
            history.record(self.db, str(i), SID, 'lifecycle', 'state_change: ready', now)
        history.record(self.db, 'old', SID, 'lifecycle', 'old', now-31*86400)
        self.db.commit()
        history.ingest(self.worker, {})
        first = history.history(self.worker, kind='lifecycle')
        self.assertEqual(len(first['events']),100)
        second = history.history(self.worker,before=first['next_before'],kind='lifecycle')
        self.assertEqual(len(second['events']),5)
        self.assertFalse(set(e['id'] for e in first['events']) & set(e['id'] for e in second['events']))
        with patch.object(history, 'MAX_EVENTS', 10):
            history.ingest(self.worker,{})
        self.assertEqual(len(history.history(self.worker)['events']),10)
        for aid,action in [('../bad','resolve'),('b'*32,'delete'),('b'*32,'resolve')]:
            with self.assertRaises(ValueError):history.transition(self.worker,aid,action)
        for before,kind in [(-1,None),(None,'SECRET')]:
            with self.assertRaises(ValueError):history.history(self.worker,before,kind)


if __name__ == '__main__':unittest.main()

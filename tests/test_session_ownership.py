import contextlib
import hashlib
import pathlib
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT=pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'scripts'))
from manage_codex_session import Worker,WorkerError,RUNTIME
import security_history
import console_observability


class OwnershipTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.temp.name)/'state';self.workers=[]
        self.a=self.worker('member-a');self.b=self.worker('member-b');self.op=self.worker('local-pilot','operator')

    def worker(self,principal,role='member'):
        w=Worker(self.root,principal,role);self.workers.append(w);return w

    def tearDown(self):
        for w in self.workers:w.db.close()
        self.temp.cleanup()

    def row(self,owner):
        import uuid
        sid=uuid.uuid4().hex
        self.op.db.execute('INSERT INTO sessions(id,state,created,owner) VALUES(?,?,?,?)',(sid,'ready',time.time(),owner));self.op.db.commit()
        return sid

    def fake_create(self,w,key):
        def docker(*args,**kwargs):return '{"'+RUNTIME+'":{}}' if args[0]=='info' else ''
        with patch.object(w,'reconcile'),patch.object(w,'docker',side_effect=docker),patch.object(w,'exists',return_value=None),patch.object(w,'provision'):
            return w.create(key)

    def test_scoped_reads_stop_cleanup_attach_and_denial_audit(self):
        a,b=self.row('member-a'),self.row('member-b')
        self.assertEqual([r['id'] for r in self.a.visible_rows()],[a])
        self.assertEqual(self.a.get(a)['owner'],'member-a')
        for operation in [lambda:self.a.get(b),lambda:self.a.stop(b),lambda:self.a.cleanup(b),lambda:self.a.authorize_attach(b)]:
            with self.assertRaises(WorkerError):operation()
        self.assertEqual(self.op.get(b)['state'],'ready')
        self.assertEqual(self.op.db.execute('SELECT COUNT(*) FROM authorization_audit WHERE actor=?',('member-a',)).fetchone()[0],4)
        self.assertEqual(len(self.op.visible_rows()),2)
        with self.assertRaisesRegex(WorkerError,'attach_owner_required'):self.op.authorize_attach(a)
        self.assertEqual(self.a.authorize_attach(a)['id'],a)

    def test_owner_scoped_idempotency_member_and_global_quotas(self):
        a=self.fake_create(self.a,'same-key');b=self.fake_create(self.b,'same-key')
        self.assertNotEqual(a['id'],b['id'])
        self.assertEqual(self.fake_create(self.a,'same-key')['id'],a['id'])
        self.fake_create(self.a,'a-second')
        with self.assertRaisesRegex(WorkerError,'quota_member_sessions'):self.fake_create(self.a,'a-third')
        self.fake_create(self.b,'b-second');c=self.worker('member-c');self.fake_create(c,'c-first')
        with self.assertRaisesRegex(WorkerError,'quota_five_sessions'):self.fake_create(c,'c-second')
        self.assertEqual(self.fake_create(self.a,'same-key')['id'],a['id'])

    def test_member_reconciliation_does_not_touch_foreign_provisioning(self):
        sid=self.row('member-b')
        self.op.db.execute("UPDATE sessions SET state='provisioning' WHERE id=?",(sid,));self.op.db.commit()
        with patch.object(self.a,'cleanup') as cleanup:
            self.a.reconcile();cleanup.assert_not_called()
        self.assertEqual(self.op.get(sid)['state'],'provisioning')

    def test_per_user_volume_and_owner_label_tamper(self):
        sid=self.row('member-a')
        implicit=Worker(self.root,'member-d');self.workers.append(implicit);self.assertEqual(implicit.role,'member')
        self.assertNotEqual(self.a.volume,self.b.volume)
        self.assertTrue(self.op.volume.endswith('-pilot-workspace'))
        self.assertEqual(self.op.session_volume(sid),self.a.volume)
        obj={'Labels':{'poc.worker':self.a.namespace,'poc.session':sid,'poc.owner':hashlib.sha256(b'member-b').hexdigest()}}
        with self.assertRaisesRegex(WorkerError,'resource_ownership_mismatch'):self.a.ensure_owned(obj,sid)
        obj['Labels']['poc.owner']=hashlib.sha256(b'member-a').hexdigest();self.a.ensure_owned(obj,sid)

    def test_history_alert_audit_and_monitor_do_not_leak_other_users(self):
        a,b=self.row('member-a'),self.row('member-b');now=time.time()
        for sid in [a,b]:
            self.op.event(sid,'state_change','failed')
            security_history.record(self.op.db,sid,sid,'egress_denied',security_history.DETAILS['egress_denied'],now)
        self.op.db.commit()
        rows=security_history.history(self.a)['events'];self.assertEqual({r['session_id'] for r in rows},{a})
        own=security_history.alerts(self.a);self.assertEqual(own['counts']['open'],1)
        foreign=next(x for x in security_history.alerts(self.op)['alerts'] if x['session_id']==b)
        with self.assertRaisesRegex(ValueError,'alert_not_found'):security_history.transition(self.a,foreign['id'],'resolve')
        updated=security_history.transition(self.b,foreign['id'],'acknowledge')
        self.assertEqual(updated['actor'],'principal:member-b')
        self.assertTrue(all(x['alert_id']!=foreign['id'] for x in security_history.alerts(self.a)['audit']))
        with patch.object(self.a,'exists',return_value=None):sample=console_observability.snapshot(self.a)
        self.assertEqual({s['id'] for s in sample['sessions']},{a})
        self.assertEqual({e['session_id'] for e in sample['events']},{a})

    def test_legacy_owner_volume_and_deadline_migration_preserved(self):
        root=pathlib.Path(self.temp.name)/'legacy';root.mkdir()
        db=sqlite3.connect(root/'sessions.sqlite')
        db.execute('CREATE TABLE sessions(id TEXT PRIMARY KEY,request_key TEXT UNIQUE,state TEXT,created REAL,ready REAL,stopped REAL,failure TEXT)')
        db.execute('INSERT INTO sessions(id,state,created) VALUES(?,?,?)',('a'*32,'stopped',1));db.commit();db.close()
        w=Worker(root);self.workers.append(w)
        row=w.get('a'*32);self.assertEqual(row['owner'],'local-pilot');self.assertIsNone(row['expires'])
        self.assertEqual(w.volume,f'poc-managed-{w.namespace}-pilot-workspace')
        for bad in ['../other','Member A','', 'a'*65]:
            with self.assertRaises(WorkerError):Worker(root,bad,'member')


if __name__=='__main__':unittest.main()

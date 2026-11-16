import pathlib
import sqlite3
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'scripts'))
import alert_rules as rules
import security_history as history

SID='a'*32


class RuleTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:');self.db.row_factory=sqlite3.Row
        history.initialize(self.db)
        self.db.execute('CREATE TABLE events(sequence INTEGER PRIMARY KEY,session_id,action,state,at)')
        self.worker=SimpleNamespace(db=self.db)

    def tearDown(self):self.db.close()

    def ingest(self,now,stats=None,error=None,flows=()):
        sample={'sessions':[{'id':SID,'state':'ready','checks':[{'status':'pass'}],
                            'telemetry':stats if stats is not None else {'cpu_percent':1,'memory_percent':10,'pids':12},'error':error}],
                '_decision_records':[{'session_id':SID,'fingerprint':history.digest(str(f))} for f in flows]}
        with patch.object(history.time,'time',return_value=now):history.ingest(self.worker,sample)
        return history.alerts(self.worker)['alerts']

    def kinds(self):return {a['kind'] for a in history.alerts(self.worker)['alerts']}

    def test_egress_five_unique_observations_and_repeat_dedup(self):
        self.ingest(1000,flows=range(4));self.assertNotIn('egress_burst',self.kinds())
        self.ingest(1030,flows=range(4));self.assertNotIn('egress_burst',self.kinds())
        self.ingest(1060,flows=range(5));self.assertIn('egress_burst',self.kinds())
        alert=next(a for a in history.alerts(self.worker)['alerts'] if a['kind']=='egress_burst')
        history.transition(self.worker,alert['id'],'resolve')
        self.ingest(1090,flows=range(5))
        current=next(a for a in history.alerts(self.worker)['alerts'] if a['kind']=='egress_burst')
        self.assertEqual(current['event_count'],1);self.assertEqual(current['status'],'resolved')

    def test_denials_outside_window_do_not_combine(self):
        for t in range(1000,1301,30):self.ingest(t,flows=range(4))
        self.ingest(1330,flows=[4]);self.assertNotIn('egress_burst',self.kinds())

    def test_resource_boundary_sustained_samples_and_recovery(self):
        stats={'cpu_percent':90,'memory_percent':10,'pids':12}
        self.ingest(1000,stats);self.ingest(1030,stats)
        self.assertNotIn('resource_pressure',self.kinds())
        self.ingest(1060,stats);self.assertIn('resource_pressure',self.kinds())
        a=next(a for a in history.alerts(self.worker)['alerts'] if a['kind']=='resource_pressure')
        history.transition(self.worker,a['id'],'resolve')
        self.ingest(1090,stats);self.ingest(1120) # verified below threshold
        self.ingest(1150,stats);self.ingest(1180,stats);self.ingest(1210,stats)
        a=next(a for a in history.alerts(self.worker)['alerts'] if a['kind']=='resource_pressure')
        self.assertEqual(a['status'],'open');self.assertEqual(a['event_count'],2)

    def test_memory_and_pid_rules_and_below_threshold(self):
        for metric,threshold in [('cpu_percent',90),('memory_percent',85),('pids',112)]:
            with self.subTest(metric=metric):
                key=SID+':resource_pressure:'+metric
                self.assertFalse(rules.sustained(self.db,key,False,1000))
                self.assertFalse(rules.sustained(self.db,key,True,1000))
                self.assertFalse(rules.sustained(self.db,key,True,1030))
                self.assertTrue(rules.sustained(self.db,key,True,1060))
        for t in (2000,2030,2060):self.ingest(t,{'cpu_percent':89.9,'memory_percent':84.9,'pids':111})
        self.assertNotIn('resource_pressure',self.kinds())
        for t in (2090,2120,2150):self.ingest(t,{'cpu_percent':1,'memory_percent':85,'pids':112})
        resource=next(a for a in history.alerts(self.worker)['alerts'] if a['kind']=='resource_pressure')
        self.assertEqual(resource['event_count'],2) # one event for each metric episode

    def test_missing_long_gap_and_duplicate_samples_reset_or_do_not_advance(self):
        key='sample'
        for _ in range(4):self.assertFalse(rules.sustained(self.db,key,True,1000))
        self.assertFalse(rules.sustained(self.db,key,True,1030))
        self.assertIsNone(rules.sustained(self.db,key,None,1060))
        self.assertFalse(rules.sustained(self.db,key,True,1090))
        self.assertFalse(rules.sustained(self.db,key,True,1200))
        self.assertEqual(self.db.execute('SELECT count FROM rule_samples WHERE key=?',(key,)).fetchone()[0],1)

    def test_repeated_incomplete_samples_and_invalid_numbers(self):
        self.ingest(1000,error='sample_unavailable');self.ingest(1030,error='sample_unavailable')
        self.assertNotIn('sample_unavailable',self.kinds())
        self.ingest(1060,error='sample_unavailable');self.assertIn('sample_unavailable',self.kinds())
        for t in (1090,1120,1150):self.ingest(t,{'cpu_percent':float('nan'),'memory_percent':None,'pids':True})
        self.assertNotIn('resource_pressure',self.kinds())

    def test_sustained_sample_progress_survives_database_reopen(self):
        stats={'cpu_percent':90,'memory_percent':10,'pids':12}
        self.ingest(1000,stats);self.ingest(1030,stats)
        restored=sqlite3.connect(':memory:');restored.row_factory=sqlite3.Row
        self.db.backup(restored);self.db.close();self.db=restored
        self.worker.db=restored;history.initialize(restored)
        self.ingest(1060,stats)
        self.assertIn('resource_pressure',self.kinds())

    def test_collector_gap_clock_regression_and_review_only_catalog(self):
        self.ingest(1000);self.ingest(1090);self.assertNotIn('collector_gap',self.kinds())
        self.ingest(1181);self.assertIn('collector_gap',self.kinds())
        self.ingest(1100)
        a=next(a for a in history.alerts(self.worker)['alerts'] if a['kind']=='collector_gap')
        self.assertEqual(a['scope'],'worker');self.assertEqual(a['event_count'],2)
        data=rules.catalog();self.assertFalse(data['automatic_session_stop']);self.assertFalse(data['editable_in_ui'])
        self.assertTrue(all(r['review'] and r['trigger'] for r in data['rules']))


if __name__=='__main__':unittest.main()

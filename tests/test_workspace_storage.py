"""Owner-scoped storage metadata; no Docker daemon needed."""
import hashlib
import json
import pathlib
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'scripts'))
from manage_codex_session import Worker, WorkerError


class WorkspaceStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.worker = Worker(self.temp.name, 'member-a', 'member')

    def tearDown(self):
        self.worker.db.close()
        self.temp.cleanup()

    def volume(self):
        return {'Name': self.worker.volume, 'Driver': 'local', 'Options': None,
                'Labels': {'poc.worker': self.worker.namespace,
                           'poc.owner': hashlib.sha256(b'member-a').hexdigest()}}

    def describe(self):
        from workspace_storage import describe
        with self.worker.locked():
            return describe(self.worker)

    def test_missing_volume_is_not_created(self):
        with patch.object(self.worker, 'exists', return_value=None), patch.object(self.worker, 'docker') as docker:
            data = self.describe()
        self.assertEqual(data['state'], 'not_created')
        self.assertIsNone(data['allocated_bytes'])
        self.assertFalse(data['hard_quota_enforced'])
        docker.assert_not_called()

    def test_usage_is_owner_scoped_and_probe_read_only(self):
        for owner, state in [('member-a', 'ready'), ('member-b', 'ready'), ('member-a', 'stopped')]:
            sid = hashlib.md5((owner+state).encode()).hexdigest()
            self.worker.db.execute('INSERT INTO sessions(id,state,created,owner) VALUES(?,?,?,?)',
                                   (sid, state, time.time(), owner))
        self.worker.db.commit()
        with patch.object(self.worker, 'exists', return_value=self.volume()), patch.object(self.worker, 'docker', return_value='4\t/workspace') as docker:
            data = self.describe()
        self.assertEqual(data['owner'], 'member-a')
        self.assertEqual(data['active_sessions'], 1)
        self.assertEqual(data['allocated_bytes'], 4096)
        self.assertEqual(data['budget_bytes'], 5 * 1024**3)
        self.assertFalse(data['over_budget'])
        self.assertEqual(data['retention'], 'until_explicit_deletion')
        command = docker.call_args_list[0].args
        self.assertIn('--network=none', command)
        self.assertIn('--read-only', command)
        self.assertIn('type=volume,source='+self.worker.volume+',target=/workspace,readonly', command)
        self.assertNotIn('member-b', repr(data))

    def test_budget_is_advisory_and_threshold_is_explicit(self):
        for size, over in [(5*1024**3, False), (5*1024**3+1024, True)]:
            with patch.object(self.worker,'exists',return_value=self.volume()), patch.object(self.worker,'docker',return_value=str(size//1024)+'\t/workspace'):
                data = self.describe()
            self.assertEqual(data['over_budget'],over)
            self.assertFalse(data['hard_quota_enforced'])
            self.assertIsNone(data['quota_bytes'])

    def test_foreign_or_bind_backed_volume_is_rejected_before_probe(self):
        foreign = self.volume(); foreign['Labels']['poc.owner'] = 'foreign'
        bind = self.volume(); bind['Options'] = {'type':'none','o':'bind','device':'/'}
        for volume in [foreign, bind]:
            with self.subTest(volume=volume), patch.object(self.worker, 'exists', return_value=volume), patch.object(self.worker, 'docker') as docker:
                with self.assertRaises(WorkerError):
                    self.describe()
                docker.assert_not_called()

    def test_incomplete_or_invalid_measurement_never_reports_zero(self):
        for output in ['{"status":"incomplete","allocated_bytes":null}', 'not json',
                       '{"status":"measured","allocated_bytes":true}',
                       '{"status":"measured","allocated_bytes":-1}']:
            with self.subTest(output=output), patch.object(self.worker,'exists',return_value=self.volume()), patch.object(self.worker,'docker',return_value=output):
                data = self.describe()
                self.assertEqual(data['measurement_status'], 'incomplete')
                self.assertIsNone(data['allocated_bytes'])

    def test_probe_failure_attempts_cleanup(self):
        with patch.object(self.worker,'exists',return_value=self.volume()), patch.object(self.worker,'docker',side_effect=[WorkerError('docker_unavailable_or_timeout'),'']) as docker:
            self.assertEqual(self.describe()['measurement_status'],'incomplete')
        self.assertEqual(docker.call_args.args[:2],('rm','-f'))

    def test_cleanup_failure_is_not_reported_as_success(self):
        with patch.object(self.worker,'exists',return_value=self.volume()), patch.object(self.worker,'docker',side_effect=['{"status":"measured","allocated_bytes":0}',WorkerError('docker_operation_failed')]):
            with self.assertRaisesRegex(WorkerError,'workspace_probe_cleanup_failed'):
                self.describe()

    def test_operator_cannot_read_foreign_owner_volume(self):
        self.worker.principal='local-pilot'
        volume=self.volume()
        with patch.object(self.worker,'exists',return_value=volume), patch.object(self.worker,'docker') as docker:
            with self.assertRaisesRegex(WorkerError,'resource_ownership_mismatch'):
                self.describe()
            docker.assert_not_called()


if __name__ == '__main__':
    unittest.main()

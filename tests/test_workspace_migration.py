"""Operator cutover is explicit, verified, reversible, and never drops rollback data."""
import hashlib,json,pathlib,sys,tempfile,time,unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent.parent/'scripts'))
from manage_codex_session import Worker,WorkerError
import workspace_migration as migration
import workspace_quota as quota

class MigrationTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.w=Worker(self.tmp.name,'migration-test','member')
  self.current={'phase':'ready','identity':'a'*32,'source_identity':'b'*64,'source':{'digest':'c'*64,'entries':2,'logical_bytes':12},'target':{'digest':'c'*64,'entries':2,'logical_bytes':12}}
 def tearDown(self):self.w.db.close();self.tmp.cleanup()
 def prepare(self):
  with self.w.locked(),patch.object(quota,'call',return_value=self.current):return migration.prepare(self.w)
 def act(self,action,record):
  phrases={'cutover':'MIGRATE WORKSPACE','rollback':'ROLLBACK WORKSPACE','discard':'DISCARD STAGED COPY','finalize':'DELETE ROLLBACK COPY','abort':'ABORT STAGED COPY'}
  with self.w.locked():return migration.act(self.w,action,record['id'],phrases[action])
 def test_prepare_keeps_original_binding_and_private_record(self):
  before=self.w.volume;record=self.prepare()
  self.assertEqual(record['phase'],'prepared');self.assertEqual(before,self.w.volume);self.assertFalse(quota.enabled(self.w))
  self.assertEqual(migration.record_path(self.w).stat().st_mode&0o777,0o600)
  with self.assertRaisesRegex(WorkerError,'rollback_retained'):migration.block_deletion(self.w)
 def test_cutover_and_rollback_preserve_source_mapping(self):
  original=self.w.volume;record=self.prepare()
  with patch.object(quota,'call',return_value=self.current),patch('workspace_storage.checked_volume',return_value={'_quota':{'identity':'a'*32}}):result=self.act('cutover',record)
  self.assertEqual(result['phase'],'active');self.assertEqual(self.w.volume,original+'-quota');self.assertTrue(quota.enabled(self.w))
  with patch.object(quota,'call',return_value=self.current):result=self.act('rollback',record)
  self.assertEqual(result['phase'],'rolled_back');self.assertEqual(self.w.volume,original);self.assertFalse(quota.enabled(self.w))
 def test_changed_copy_blocks_cutover_and_rollback(self):
  record=self.prepare();changed=dict(self.current,target={'digest':'d'*64})
  for action in ['cutover','rollback']:
   with patch.object(quota,'call',return_value=changed),self.assertRaisesRegex(WorkerError,'contents_changed'):self.act(action,record)
  self.assertFalse(quota.enabled(self.w))
 def test_failed_cutover_restores_enrollment(self):
  record=self.prepare()
  with patch.object(quota,'call',return_value=self.current),patch('workspace_storage.checked_volume',side_effect=WorkerError('quota_mount_unavailable')):
   with self.assertRaisesRegex(WorkerError,'mount_unavailable'):self.act('cutover',record)
  self.assertFalse(quota.enabled(self.w));self.assertEqual(migration.read_record(self.w)['phase'],'prepared')
 def test_mismatched_confirmation_and_active_sessions_block(self):
  record=self.prepare()
  with self.assertRaisesRegex(WorkerError,'confirmation_invalid'):migration.act(self.w,'cutover',record['id'],'yes')
  self.w.db.execute('INSERT INTO sessions(id,state,created,owner) VALUES(?,?,?,?)',('f'*32,'ready',time.time(),self.w.principal));self.w.db.commit()
  with patch.object(quota,'call') as call,self.assertRaisesRegex(WorkerError,'workspace_in_use'):self.act('cutover',record)
  call.assert_not_called()
 def test_staged_discard_requires_inactive_owner(self):
  record=self.prepare()
  with patch.object(quota,'call',return_value=self.current),patch.object(quota,'remove') as remove:result=self.act('discard',record)
  remove.assert_called_once_with(self.w,'a'*32);self.assertEqual(result['phase'],'discarded');migration.block_deletion(self.w)
 def test_finalize_is_explicit_and_resumable(self):
  record=self.prepare();migration.enrollment(self.w,True);record['phase']='finalizing';migration.atomic(migration.record_path(self.w),record)
  with patch('workspace_storage.checked_volume',return_value={'_quota':{'identity':'a'*32}}),patch.object(quota,'call',return_value={'finalized':True}):result=self.act('finalize',record)
  self.assertEqual(result['phase'],'finalized');self.assertTrue(quota.enabled(self.w));migration.block_deletion(self.w)
 def test_abort_when_preflight_never_created_storage(self):
  record={'id':'a'*32,'namespace':self.w.namespace,'owner':self.w.principal,'phase':'copying'};migration.atomic(migration.record_path(self.w),record)
  with patch.object(quota,'call',side_effect=[WorkerError('migration_not_prepared'),{'state':'absent'}]):result=self.act('abort',record)
  self.assertEqual(result['phase'],'discarded');migration.block_deletion(self.w)

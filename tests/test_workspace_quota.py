"""Optional quota backend: no fallbacks, untrusted mounts, or metadata-only deletion."""
import hashlib,json,pathlib,sys,tempfile,time,unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent.parent/'scripts'))
from manage_codex_session import Worker,WorkerError,RUNTIME
import workspace_quota as quota
from workspace_storage import checked_volume,describe
from workspace_lifecycle import prepare_deletion,delete_workspace

class QuotaBindingTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.w=Worker(self.tmp.name,'member-a','member')
  self.volume={'Name':self.w.volume,'CreatedAt':'2026-11-15T00:00:00Z','Driver':'local','Options':{'type':'none','o':'bind','device':'/fixed/canary'},'Labels':{'poc.worker':self.w.namespace,'poc.owner':hashlib.sha256(b'member-a').hexdigest(),'poc.storage':'xfs-project-v1','poc.storage-id':'a'*32}}
  self.snapshot={'state':'ready','backend':'xfs-project-v1','volume':self.w.volume,'identity':'a'*32,'hard_quota_enforced':True,'quota_bytes':quota.LIMIT,'quota_used_bytes':4096,'quota_remaining_bytes':quota.LIMIT-4096,'options':self.volume['Options']}
 def tearDown(self):self.w.db.close();self.tmp.cleanup()
 def enroll(self):
  path=self.w.root/'quota-owners.json';path.write_text(json.dumps({'owners':['member-a']}));path.chmod(0o600);return path
 def test_dangling_config_symlink_is_not_legacy_fallback(self):
  (self.w.root/'quota-owners.json').symlink_to(self.w.root/'missing')
  with self.assertRaisesRegex(WorkerError,'quota_config_invalid'):quota.enabled(self.w)
 def test_enrollment_scoped_and_private(self):
  self.assertFalse(quota.enabled(self.w));path=self.enroll();self.assertTrue(quota.enabled(self.w))
  self.w.principal='member-b';self.assertFalse(quota.enabled(self.w));self.w.principal='member-a'
  path.chmod(0o644)
  with self.assertRaisesRegex(WorkerError,'quota_config_invalid'):quota.enabled(self.w)
 def test_custom_volume_without_enrollment_rejected(self):
  with patch.object(self.w,'exists',return_value=self.volume),patch.object(quota,'call') as call:
   with self.assertRaisesRegex(WorkerError,'workspace_storage_unsupported'):checked_volume(self.w)
   call.assert_not_called()
 def test_verified_quota_metadata_and_probe(self):
  self.enroll()
  with patch.object(self.w,'exists',return_value=self.volume),patch.object(quota,'call',return_value=self.snapshot),patch.object(self.w,'docker',return_value='4 /workspace'):
   with self.w.locked():data=describe(self.w)
  self.assertTrue(data['hard_quota_enforced']);self.assertEqual(data['quota_bytes'],quota.LIMIT)
  self.assertEqual(data['quota_remaining_bytes'],quota.LIMIT-4096)
  self.assertNotIn('/fixed/canary',json.dumps(data));self.assertNotIn('identity',data)
 def test_unavailable_mount_blocks_probe_and_attach(self):
  self.enroll();self.w.db.execute('INSERT INTO sessions(id,state,created,owner) VALUES(?,?,?,?)',('b'*32,'ready',time.time(),self.w.principal));self.w.db.commit()
  with patch.object(self.w,'exists',return_value=self.volume),patch.object(quota,'call',side_effect=WorkerError('quota_mount_unavailable')),patch.object(self.w,'docker') as docker:
   with self.assertRaisesRegex(WorkerError,'quota_mount_unavailable'):checked_volume(self.w)
   with self.assertRaisesRegex(WorkerError,'quota_mount_unavailable'):self.w.authorize_attach('b'*32)
   docker.assert_not_called()
 def test_snapshot_mismatch_rejected(self):
  for data in [[],{},dict(self.snapshot,hard_quota_enforced=False),dict(self.snapshot,quota_bytes=quota.LIMIT+1),dict(self.snapshot,volume='foreign'),dict(self.snapshot,identity='b'*32),dict(self.snapshot,quota_remaining_bytes=-1)]:
   with self.subTest(data=data),self.assertRaises(WorkerError):quota.validate(self.w,self.volume,data)
 def test_create_failure_never_creates_ordinary_volume(self):
  self.enroll()
  def docker(*args,**kwargs):return json.dumps({RUNTIME:{}}) if args[0]=='info' else ''
  with patch.object(self.w,'reconcile'),patch.object(self.w,'docker',side_effect=docker) as docker_mock,patch.object(quota,'call',side_effect=WorkerError('quota_pool_capacity')),patch.object(self.w,'provision') as provision:
   with self.assertRaisesRegex(WorkerError,'quota_pool_capacity'):self.w.create('canary')
   self.assertFalse(any(c.args[:2]==('volume','create') for c in docker_mock.call_args_list));provision.assert_not_called()
 def test_backing_deletion_failure_is_unknown_not_metadata_success(self):
  self.enroll()
  with patch.object(self.w,'exists',return_value=self.volume),patch.object(quota,'call',return_value=self.snapshot),patch.object(self.w,'docker',return_value=''):
   with self.w.locked():ticket=prepare_deletion(self.w)
  with patch.object(self.w,'exists',return_value=self.volume),patch.object(quota,'call',return_value=self.snapshot),patch.object(self.w,'docker',return_value='') as docker,patch.object(quota,'remove',side_effect=WorkerError('quota_storage_unavailable')):
   with self.w.locked(),self.assertRaisesRegex(WorkerError,'workspace_delete_unknown'):delete_workspace(self.w,ticket['token'],'DELETE WORKSPACE')
   self.assertFalse(any(c.args[:2]==('volume','rm') for c in docker.call_args_list))
  self.assertEqual(self.w.db.execute("SELECT outcome FROM authorization_audit WHERE action='delete_workspace'").fetchone()[0],'unknown')
 def test_remove_requires_backing_absence(self):
  with patch.object(quota,'call',side_effect=[{'deleted':True},self.snapshot]):
   with self.assertRaisesRegex(WorkerError,'quota_deletion_unverified'):quota.remove(self.w,'a'*32)
 def test_root_protocol_error_is_sanitized(self):
  from types import SimpleNamespace
  for stderr in ['private raw diagnostic','{"error":"not-safe/../../"}']:
   with patch.object(quota.subprocess,'run',return_value=SimpleNamespace(returncode=1,stderr=stderr,stdout='')):
    with self.assertRaisesRegex(WorkerError,'quota_storage_unavailable'):quota.call(self.w,'status')

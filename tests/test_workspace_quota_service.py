"""Root storage-service boundaries tested without mounts, sudo, or Docker."""
import os,pathlib,stat,sys,tempfile,unittest
from types import SimpleNamespace
from unittest.mock import patch,Mock
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent.parent/'scripts'))
import workspace_quota_service as service

class ServiceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.directory=pathlib.Path(self.tmp.name)/'new'
  self.data={'namespace':'a'*10,'owner':'canary','identity':'b'*32,'phase':'ready','uuid':'fixture-uuid','volume':'fixture-volume','quota_bytes':service.QUOTA}
 def tearDown(self):self.tmp.cleanup()
 def test_binding_rejects_external_paths_and_unknown_namespace(self):
  with patch.object(service,'load',return_value={'workers':{}}),patch.object(service,'trusted'),patch.dict(os.environ,{'SUDO_UID':'501'}):
   for namespace,owner in [('../outside','owner'),('a'*10,'../../root'),('a'*10,'owner')]:
    with self.assertRaises(service.StorageError):service.binding(namespace,owner)
 def test_worker_uid_boundary(self):
  import hashlib
  state='/registered/state';namespace=hashlib.sha256(state.encode()).hexdigest()[:10]
  with patch.object(service,'load',return_value={'workers':{namespace:{'state_dir':state,'uid':501}}}),patch.object(service,'trusted'),patch.dict(os.environ,{'SUDO_UID':'502'}):
   with self.assertRaisesRegex(service.StorageError,'not_authorized'):service.binding(namespace,'canary')
 def test_metadata_rejects_symlink_nonroot_and_writable(self):
  for mode,uid in [(stat.S_IFLNK|0o777,0),(stat.S_IFREG|0o600,501),(stat.S_IFREG|0o666,0)]:
   path=Mock();path.lstat.return_value=SimpleNamespace(st_mode=mode,st_uid=uid)
   with self.assertRaisesRegex(service.StorageError,'untrusted'):service.trusted(path)
 def test_missing_or_wrong_mount_refused(self):
  for mount in [None,{'source':'/dev/loop9','fstype':'xfs','options':'rw,prjquota,nosuid,nodev'},
                {'source':'/dev/loop1','fstype':'ext4','options':'rw,prjquota,nosuid,nodev'},
                {'source':'/dev/loop1','fstype':'xfs','options':'rw,nosuid,nodev'}]:
   with patch.object(service,'mount_record',return_value=mount),patch.object(service,'loop_for',return_value='/dev/loop1'),patch.object(service,'run') as run:
    with self.assertRaisesRegex(service.StorageError,'mount_unavailable'):service.validate_mount(self.directory,self.data)
    run.assert_not_called()
 def test_filesystem_uuid_and_enforcement_must_match(self):
  mount={'source':'/dev/loop1','fstype':'xfs','options':'rw,prjquota,nosuid,nodev'}
  with patch.object(service,'mount_record',return_value=mount),patch.object(service,'loop_for',return_value='/dev/loop1'),patch.object(service,'run',return_value='foreign'):
   with self.assertRaisesRegex(service.StorageError,'filesystem_mismatch'):service.validate_mount(self.directory,self.data)
  with patch.object(service,'mount_record',return_value=mount),patch.object(service,'loop_for',return_value='/dev/loop1'),patch.object(service,'run',return_value='fixture-uuid'),patch.object(service,'quota_command',return_value='Accounting: ON\nEnforcement: OFF'):
   with self.assertRaisesRegex(service.StorageError,'enforcement_unavailable'):service.validate_mount(self.directory,self.data)
 def test_numeric_limit_change_refused(self):
  mount={'source':'/dev/loop1','fstype':'xfs','options':'rw,prjquota,nosuid,nodev'}
  with patch.object(service,'mount_record',return_value=mount),patch.object(service,'loop_for',return_value='/dev/loop1'),patch.object(service,'run',return_value='fixture-uuid'),patch.object(service,'quota_command',side_effect=['Accounting: ON\nEnforcement: ON','/dev/loop1 0 0 6291456']):
   with self.assertRaisesRegex(service.StorageError,'limit_mismatch'):service.validate_mount(self.directory,self.data)
 def test_quota_readback_malformed_or_ambiguous_refused(self):
  for text in ['', '/dev/loop1 0 0 nope','/dev/loop1 -1 0 5242880','/dev/loop1 0 0 1\n/dev/loop1 0 0 2']:
   with self.assertRaisesRegex(service.StorageError,'readback_invalid'):service.quota_values(text,'/dev/loop1')
 def test_foreign_volume_options_refused(self):
  with patch.object(service,'volume_record',return_value={'Driver':'local','Options':{'device':'/etc'},'Labels':service.labels(self.data)}):
   with self.assertRaisesRegex(service.StorageError,'volume_mismatch'):service.validate_volume(self.directory,self.data)
 def test_active_or_stopped_reference_prevents_backing_deletion(self):
  with patch.object(service,'manifest',return_value=(self.directory,self.data)),patch.object(service,'validate_mount'),patch.object(service,'validate_volume',return_value={}),patch.object(service,'run',return_value='stopped-container'),patch.object(service,'write') as write:
   with self.assertRaisesRegex(service.StorageError,'workspace_in_use'):service.delete('a'*10,'canary','b'*32)
   write.assert_not_called()
 def test_wrong_identity_cannot_delete(self):
  with patch.object(service,'manifest',return_value=(self.directory,self.data)),patch.object(service,'validate_mount') as validate:
   with self.assertRaisesRegex(service.StorageError,'identity_changed'):service.delete('a'*10,'canary','c'*32)
   validate.assert_not_called()
 def test_interrupted_deletion_never_recreates_old_data(self):
  data=dict(self.data,phase='deleting')
  with patch.object(service,'manifest',return_value=(self.directory,data)),patch.object(service,'run') as run:
   with self.assertRaisesRegex(service.StorageError,'incomplete'):service.create('a'*10,'canary')
   run.assert_not_called()
 def test_existing_legacy_volume_requires_migration(self):
  with patch.object(service,'manifest',return_value=(self.directory,None)),patch.object(service,'binding',return_value=(self.directory,'fixture-volume','hash')),patch.object(service,'volume_record',return_value={'Driver':'local'}):
   with self.assertRaisesRegex(service.StorageError,'migration_required'):service.create('a'*10,'canary')
   self.assertFalse(self.directory.exists())
 def test_pool_capacity_checked_before_creating_image(self):
  with patch.object(service,'manifest',return_value=(self.directory,None)),patch.object(service,'binding',return_value=(self.directory,'fixture-volume','hash')),patch.object(service,'volume_record',return_value=None),patch.object(service.shutil,'disk_usage',return_value=SimpleNamespace(free=service.IMAGE_BYTES)):
   with self.assertRaisesRegex(service.StorageError,'pool_capacity'):service.create('a'*10,'canary')
   self.assertFalse(self.directory.exists())

 def test_deleting_phase_committed_before_volume_removal(self):
  def command(*args,**kwargs):
   if args[:3]==('docker','volume','rm'):
    self.assertEqual(self.data['phase'],'deleting')
    raise service.StorageError('quota_storage_command_failed')
   return ''
  with patch.object(service,'manifest',return_value=(self.directory,self.data)),patch.object(service,'validate_mount'),patch.object(service,'validate_volume',return_value={'Name':'fixture-volume'}),patch.object(service,'run',side_effect=command),patch.object(service,'write') as write:
   with self.assertRaises(service.StorageError):service.delete('a'*10,'canary','b'*32)
   self.assertEqual(write.call_args.args[1]['phase'],'deleting')
 def test_lost_disk_reservation_refused_before_loop_attachment(self):
  info=SimpleNamespace(st_size=service.IMAGE_BYTES,st_blocks=service.IMAGE_BYTES//512-1)
  with patch.object(service,'trusted'),patch.object(pathlib.Path,'stat',return_value=info),patch.object(service,'run') as run:
   with self.assertRaisesRegex(service.StorageError,'reservation_missing'):service.loop_for(self.directory,attach=True)
   run.assert_not_called()

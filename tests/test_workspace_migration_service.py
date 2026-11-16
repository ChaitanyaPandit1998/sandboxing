"""Root migration operations must retain originals and reject stale identities."""
import pathlib,sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent.parent/'scripts'))
import workspace_quota_service as service

class RootMigrationTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=pathlib.Path(self.tmp.name)
  self.data={'phase':'ready','identity':'a'*32,'legacy_volume':'legacy','source_identity':'b'*64,'migration_digest':'c'*64,'volume':'legacy-quota','namespace':'d'*10,'owner':'owner','uuid':'fixture'}
 def tearDown(self):self.tmp.cleanup()
 def test_changed_original_identity_prevents_backup_cleanup(self):
  with patch.object(service,'manifest',return_value=(self.path,self.data)),patch.object(service,'binding',return_value=(self.path,'legacy','hash')),patch.object(service,'validate_mount'),patch.object(service,'validate_volume'),patch.object(service,'run',return_value='') as run,patch.object(service,'volume_record',return_value={}),patch.object(service,'legacy_source',return_value=(self.path,'legacy','different')),patch('workspace_copy.inventory',return_value={'digest':'c'*64}):
   with self.assertRaisesRegex(service.StorageError,'source_changed'):service.finalize_migration('d'*10,'owner','a'*32)
   self.assertFalse(any(c.args[:3]==('docker','volume','rm') for c in run.call_args_list))
 def test_unexpected_missing_backup_is_not_finalized(self):
  with patch.object(service,'manifest',return_value=(self.path,self.data)),patch.object(service,'binding',return_value=(self.path,'legacy','hash')),patch.object(service,'validate_mount'),patch.object(service,'validate_volume'),patch.object(service,'run',return_value=''),patch.object(service,'volume_record',return_value=None),patch.object(service,'write') as write:
   with self.assertRaisesRegex(service.StorageError,'backup_missing'):service.finalize_migration('d'*10,'owner','a'*32)
   write.assert_not_called()
 def test_abort_refuses_changed_staged_data(self):
  with patch.object(service,'manifest',return_value=(self.path,self.data)),patch.object(service,'legacy_source',return_value=(self.path,'legacy','b'*64)),patch('workspace_copy.inventory',side_effect=[{'digest':'c'*64},{'digest':'changed'}]),patch.object(service,'delete') as delete:
   with self.assertRaisesRegex(service.StorageError,'abort_refused'):service.abort_migration('d'*10,'owner','a'*32)
   delete.assert_not_called()
 def test_migrated_recreation_refuses_an_unreviewed_legacy_volume(self):
  target=self.path/'target'
  with patch.object(service,'manifest',return_value=(target,None)),patch.object(service,'binding',return_value=(target,'legacy','hash')),patch.object(service,'volume_record',return_value={'Name':'legacy'}):
   with self.assertRaisesRegex(service.StorageError,'migration_required'):service.create('d'*10,'owner',alternate=True)
   self.assertFalse(target.exists())

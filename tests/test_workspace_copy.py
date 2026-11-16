"""Migration copies without extraction, path following, or content in reports."""
import importlib.util,os,pathlib,tempfile,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parent.parent

class CopyTests(unittest.TestCase):
 def setUp(self):
  if not hasattr(os,'listxattr'):
   self.xattrs=patch.object(os,'listxattr',return_value=[],create=True);self.xattrs.start();self.addCleanup(self.xattrs.stop)
  self.tmp=tempfile.TemporaryDirectory();self.source=pathlib.Path(self.tmp.name)/'source';self.target=pathlib.Path(self.tmp.name)/'target';self.source.mkdir();self.target.mkdir()
 def tearDown(self):self.tmp.cleanup()
 def module(self):
  spec=importlib.util.spec_from_file_location('workspace_copy',ROOT/'scripts/workspace_copy.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
 def fixture(self):
  (self.source/'nested').mkdir();file=self.source/'nested/file';file.write_bytes(b'private fixture bytes');file.chmod(0o640)
  os.link(file,self.source/'hardlink');(self.source/'link').symlink_to('nested/file');(self.source/'external').symlink_to('/not/read/by/migration')
 def test_content_metadata_links_and_empty_directories(self):
  m=self.module();self.fixture();(self.source/'empty').mkdir()
  before=m.inventory(self.source);m.copy_verified(self.source,self.target)
  self.assertEqual(before,m.inventory(self.target));self.assertEqual(before,m.inventory(self.source))
  self.assertEqual((self.target/'hardlink').stat().st_ino,(self.target/'nested/file').stat().st_ino)
  self.assertEqual(os.readlink(self.target/'external'),'/not/read/by/migration')
  self.assertNotIn('private fixture',str(before));self.assertNotIn('nested/file',str(before))
 def test_special_files_rejected_before_copy(self):
  m=self.module();os.mkfifo(self.source/'fifo')
  with self.assertRaisesRegex(m.CopyError,'unsupported'):m.copy_verified(self.source,self.target)
  self.assertEqual(list(self.target.iterdir()),[])
 def test_nonempty_target_is_never_overwritten(self):
  m=self.module();(self.target/'keep').write_text('keep')
  with self.assertRaisesRegex(m.CopyError,'target_not_empty'):m.copy_verified(self.source,self.target)
  self.assertEqual((self.target/'keep').read_text(),'keep')
 def test_mutated_copy_is_detected(self):
  m=self.module();self.fixture();m.copy_verified(self.source,self.target)
  (self.target/'nested/file').write_text('changed')
  self.assertNotEqual(m.inventory(self.source)['digest'],m.inventory(self.target)['digest'])
 def test_entry_and_size_limits(self):
  m=self.module();(self.source/'big').write_bytes(b'12345')
  with self.assertRaisesRegex(m.CopyError,'size_limit'):m.inventory(self.source,max_bytes=4)
  with self.assertRaisesRegex(m.CopyError,'entry_limit'):m.inventory(self.source,max_entries=1)

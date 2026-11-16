"""Fail-closed guards for a privileged, explicitly opt-in disposable test."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from contextlib import ExitStack

spec=importlib.util.spec_from_file_location('quota_probe',Path(__file__).resolve().parent.parent/'scripts/test_workspace_quota_live.py')
probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)

class QuotaProbeTests(unittest.TestCase):
 def guarded(self,argv,uid=0,host='lima-gvisor-poc',tool='/test/tool',free=10*probe.GIB):
  stack=ExitStack();self.addCleanup(stack.close)
  stack.enter_context(patch('sys.argv',['quota-probe',*argv]))
  stack.enter_context(patch.object(probe.os,'geteuid',return_value=uid))
  stack.enter_context(patch.object(probe.os,'uname',return_value=SimpleNamespace(nodename=host)))
  stack.enter_context(patch.object(probe.shutil,'which',return_value=tool))
  stack.enter_context(patch.object(probe.shutil,'disk_usage',return_value=SimpleNamespace(free=free)))
  run=stack.enter_context(patch.object(probe,'run'))
  temp=stack.enter_context(patch.object(probe.tempfile,'mkdtemp',side_effect=AssertionError('storage creation forbidden in guard test')))
  return run,temp
 def test_opt_in_required(self):
  run,temp=self.guarded([])
  with self.assertRaisesRegex(SystemExit,'explicit opt-in'):probe.main()
  run.assert_not_called();temp.assert_not_called()
 def test_nonroot_rejected(self):
  run,temp=self.guarded(['--allow-disposable-storage-test'],uid=501)
  with self.assertRaisesRegex(SystemExit,'as root'):probe.main()
  run.assert_not_called();temp.assert_not_called()
 def test_other_host_rejected(self):
  run,temp=self.guarded(['--allow-disposable-storage-test'],host='production')
  with self.assertRaisesRegex(SystemExit,'lima-gvisor-poc'):probe.main()
  run.assert_not_called();temp.assert_not_called()
 def test_missing_tool_rejected(self):
  run,temp=self.guarded(['--allow-disposable-storage-test'],tool=None)
  with self.assertRaisesRegex(SystemExit,'Missing tool'):probe.main()
  run.assert_not_called();temp.assert_not_called()
 def test_low_space_rejected_before_storage_mutation(self):
  run,temp=self.guarded(['--allow-disposable-storage-test'],free=8*probe.GIB)
  with self.assertRaisesRegex(SystemExit,'9 GiB'):probe.main()
  run.assert_not_called();temp.assert_not_called()
 def test_quota_readback_uses_filesystem_row(self):
  self.assertEqual(probe.hard_limit_kib('/dev/loop3 0 0 5242880 00 [--------] /fixture','/dev/loop3'),5242880)
 def test_missing_malformed_and_ambiguous_readback_is_unknown(self):
  for report in ['', '1001 0 0 5242880', '/dev/loop3 0 0 unknown', '/dev/loop3 0 0 -1', '/dev/loop3 0 0 1\n/dev/loop3 0 0 2']:
   with self.subTest(report=report):self.assertIsNone(probe.hard_limit_kib(report,'/dev/loop3'))

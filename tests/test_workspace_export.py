"""Export boundaries tested without a Docker daemon."""
import io
import tarfile
import sys
import pathlib
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent.parent/'scripts'))
from manage_codex_session import Worker, WorkerError


def archive(name='file.txt', kind=tarfile.REGTYPE, contents=b'fixture'):
    output=io.BytesIO()
    with tarfile.open(fileobj=output,mode='w',format=tarfile.USTAR_FORMAT) as tar:
        item=tarfile.TarInfo(name); item.type=kind
        item.linkname='/etc/passwd' if kind in (tarfile.SYMTYPE,tarfile.LNKTYPE) else ''
        item.size=len(contents) if kind==tarfile.REGTYPE else 0
        tar.addfile(item,io.BytesIO(contents) if item.size else None)
    return output.getvalue()


class ExportTests(unittest.TestCase):
    def test_valid_archive_and_empty_directory(self):
        from workspace_export import validate_archive
        validate_archive(archive());validate_archive(archive('.',tarfile.DIRTYPE))

    def test_unsafe_entries_rejected(self):
        from workspace_export import validate_archive
        for name,kind in [('../outside',tarfile.REGTYPE),('/outside',tarfile.REGTYPE),
                          ('C:/outside',tarfile.REGTYPE),('a\\..\\outside',tarfile.REGTYPE),
                          ('.',tarfile.REGTYPE),('control\nfile',tarfile.REGTYPE),
                          ('link',tarfile.SYMTYPE),('hard',tarfile.LNKTYPE),('fifo',tarfile.FIFOTYPE),
                          ('dev',tarfile.CHRTYPE),('a/../../outside',tarfile.REGTYPE)]:
            with self.subTest(name=name,kind=kind),self.assertRaises(WorkerError):
                validate_archive(archive(name,kind))

    def test_corrupt_and_oversize_rejected(self):
        from workspace_export import validate_archive
        for value in [b'bad',b'',b'x'*(16*1024**2+1),archive()[:600]]:
            with self.assertRaises(WorkerError):validate_archive(value)

    def test_owner_and_active_checks_precede_export(self):
        from workspace_export import export_workspace
        from test_workspace_storage import WorkspaceStorageTests
        fixture=WorkspaceStorageTests();fixture.setUp();w=fixture.worker
        try:
            with patch.object(w,'exists',return_value=fixture.volume()),patch.object(w,'docker',return_value='orphan'),patch('workspace_export.capture_archive') as capture:
                with w.locked(),self.assertRaisesRegex(WorkerError,'workspace_in_use'):export_workspace(w)
                capture.assert_not_called()
            foreign=fixture.volume();foreign['Labels']['poc.owner']='foreign'
            with patch.object(w,'exists',return_value=foreign),patch.object(w,'docker') as docker:
                with w.locked(),self.assertRaises(WorkerError):export_workspace(w)
                docker.assert_not_called()
        finally:fixture.tearDown()

    def test_missing_workspace_is_not_created(self):
        from workspace_export import export_workspace
        with tempfile.TemporaryDirectory() as root:
            w=Worker(root,'member-a','member')
            try:
                with patch.object(w,'exists',return_value=None),patch.object(w,'docker') as docker:
                    with w.locked(),self.assertRaisesRegex(WorkerError,'workspace_not_found'):export_workspace(w)
                    docker.assert_not_called()
            finally:w.db.close()

    def test_export_cleans_probe_and_returns_archive(self):
        import base64
        from workspace_export import export_workspace
        from test_workspace_storage import WorkspaceStorageTests
        fixture=WorkspaceStorageTests();fixture.setUp();w=fixture.worker
        try:
            with patch.object(w,'exists',return_value=fixture.volume()),patch.object(w,'docker',return_value='') as docker,patch('workspace_export.capture_archive',return_value=archive()) as capture:
                with w.locked():result=export_workspace(w)
                self.assertEqual(base64.b64decode(result['archive_base64']),archive())
                self.assertIn('--network=none',capture.call_args.args[0]);self.assertIn('--user=10001:10001',capture.call_args.args[0])
                self.assertEqual(docker.call_args.args[:2],('rm','-f'))
        finally:fixture.tearDown()

    def test_active_session_blocks_even_if_no_running_container(self):
        from workspace_export import export_workspace
        from test_workspace_storage import WorkspaceStorageTests
        fixture=WorkspaceStorageTests();fixture.setUp();w=fixture.worker
        try:
            w.db.execute("INSERT INTO sessions(id,state,created,owner) VALUES(?,?,?,?)",('a'*32,'ready',1,w.principal));w.db.commit()
            with patch.object(w,'exists',return_value=fixture.volume()),patch.object(w,'docker') as docker:
                with w.locked(),self.assertRaisesRegex(WorkerError,'workspace_in_use'):export_workspace(w)
                docker.assert_not_called()
        finally:fixture.tearDown()

    def test_failure_cleans_probe_and_cleanup_failure_is_visible(self):
        from workspace_export import export_workspace
        from test_workspace_storage import WorkspaceStorageTests
        fixture=WorkspaceStorageTests();fixture.setUp();w=fixture.worker
        try:
            with patch.object(w,'exists',return_value=fixture.volume()),patch.object(w,'docker',return_value='') as docker,patch('workspace_export.capture_archive',side_effect=WorkerError('workspace_export_timeout')):
                with w.locked(),self.assertRaisesRegex(WorkerError,'workspace_export_timeout'):export_workspace(w)
                self.assertEqual(docker.call_args.args[:2],('rm','-f'))
            with patch.object(w,'exists',return_value=fixture.volume()),patch.object(w,'docker',side_effect=['',WorkerError('docker_operation_failed')]),patch('workspace_export.capture_archive',return_value=archive()):
                with w.locked(),self.assertRaisesRegex(WorkerError,'workspace_probe_cleanup_failed'):export_workspace(w)
        finally:fixture.tearDown()

    def test_capture_limit_and_timeout(self):
        from workspace_export import capture_archive
        with self.assertRaisesRegex(WorkerError,'workspace_export_too_large'):
            capture_archive([sys.executable,'-c','import sys;sys.stdout.buffer.write(b"x"*4096)'],limit=1024)
        with self.assertRaisesRegex(WorkerError,'workspace_export_timeout'):
            capture_archive([sys.executable,'-c','import time;time.sleep(5)'],timeout=.05)
        self.assertEqual(capture_archive([sys.executable,'-c','print("ok",end="")']),b'ok')

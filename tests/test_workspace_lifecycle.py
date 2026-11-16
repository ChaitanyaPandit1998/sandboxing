"""Disposable SQLite and mocked Docker tests for explicit deletion consent."""
import hashlib,pathlib,sys,tempfile,time,unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent.parent/'scripts'))
from manage_codex_session import Worker,WorkerError

class LifecycleTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.w=Worker(self.tmp.name,'member-a','member')
  self.volume={'Name':self.w.volume,'CreatedAt':'2026-11-15T00:00:00Z','Driver':'local','Options':None,'Labels':{'poc.worker':self.w.namespace,'poc.owner':hashlib.sha256(b'member-a').hexdigest()}}
 def tearDown(self):self.w.db.close();self.tmp.cleanup()
 def prepare(self):
  from workspace_lifecycle import prepare_deletion
  with self.w.locked():return prepare_deletion(self.w)
 def delete(self,token,confirmation='DELETE WORKSPACE'):
  from workspace_lifecycle import delete_workspace
  with self.w.locked():return delete_workspace(self.w,token,confirmation)
 def test_confirmation_deleted_and_token_cannot_be_replayed(self):
  with patch.object(self.w,'exists',return_value=self.volume),patch.object(self.w,'docker',return_value=''):
   ticket=self.prepare()
  with patch.object(self.w,'exists',side_effect=[self.volume,None]),patch.object(self.w,'docker',return_value='') as docker:
   self.assertTrue(self.delete(ticket['token'])['deleted'])
   self.assertEqual(docker.call_args_list[-2].args,('volume','rm',self.w.volume))
  with patch.object(self.w,'exists',return_value=self.volume),patch.object(self.w,'docker',return_value='') as docker:
   with self.assertRaisesRegex(WorkerError,'workspace_confirmation_invalid'):self.delete(ticket['token'])
   docker.assert_not_called()
  row=self.w.db.execute("SELECT * FROM authorization_audit WHERE action='delete_workspace'").fetchone()
  self.assertEqual(row['outcome'],'deleted');self.assertEqual(row['actor'],'member-a')
 def test_wrong_phrase_and_foreign_token_do_not_delete(self):
  with patch.object(self.w,'exists',return_value=self.volume),patch.object(self.w,'docker',return_value=''):
   ticket=self.prepare()
  for token,phrase in [(ticket['token'],'delete'),('f'*64,'DELETE WORKSPACE')]:
   with patch.object(self.w,'docker') as docker:
    with self.assertRaises(WorkerError):self.delete(token,phrase)
    docker.assert_not_called()
  self.w.principal='member-b'
  with patch.object(self.w,'docker') as docker:
   with self.assertRaises(WorkerError):self.delete(ticket['token'])
   docker.assert_not_called()
 def test_expired_and_replaced_workspace_are_rejected(self):
  with patch.object(self.w,'exists',return_value=self.volume),patch.object(self.w,'docker',return_value=''):
   expired=self.prepare();ticket=self.prepare()
  self.w.db.execute('UPDATE workspace_deletions SET expires=0 WHERE token_hash=?',(hashlib.sha256(expired['token'].encode()).hexdigest(),));self.w.db.commit()
  with patch.object(self.w,'docker') as docker:
   with self.assertRaisesRegex(WorkerError,'workspace_confirmation_invalid'):self.delete(expired['token'])
   docker.assert_not_called()
  replacement=dict(self.volume,CreatedAt='2026-11-15T00:01:00Z')
  with patch.object(self.w,'exists',return_value=replacement),patch.object(self.w,'docker') as docker:
   with self.assertRaisesRegex(WorkerError,'workspace_changed'):self.delete(ticket['token'])
   docker.assert_not_called()
 def test_active_and_stopped_container_references_block(self):
  with patch.object(self.w,'exists',return_value=self.volume),patch.object(self.w,'docker',return_value='container') as docker:
   with self.assertRaisesRegex(WorkerError,'workspace_in_use'):self.prepare()
   self.assertEqual(docker.call_args.args[:2],('ps','-aq'))
  self.w.db.execute('INSERT INTO sessions(id,state,created,owner) VALUES(?,?,?,?)',('a'*32,'ready',1,self.w.principal));self.w.db.commit()
  with patch.object(self.w,'exists',return_value=self.volume),patch.object(self.w,'docker') as docker:
   with self.assertRaisesRegex(WorkerError,'workspace_in_use'):self.prepare()
   docker.assert_not_called()
 def test_prepare_missing_foreign_and_bind_mount_rejected(self):
  for volume in [None,dict(self.volume,Labels={'poc.worker':self.w.namespace,'poc.owner':'foreign'}),dict(self.volume,Options={'o':'bind'})]:
   with patch.object(self.w,'exists',return_value=volume),patch.object(self.w,'docker') as docker:
    with self.assertRaises(WorkerError):self.prepare()
    docker.assert_not_called()
 def test_docker_failure_is_audited_and_token_consumed(self):
  with patch.object(self.w,'exists',return_value=self.volume),patch.object(self.w,'docker',return_value=''):ticket=self.prepare()
  with patch.object(self.w,'exists',return_value=self.volume),patch.object(self.w,'docker',side_effect=['',WorkerError('docker_operation_failed'),self.w.volume]):
   with self.assertRaisesRegex(WorkerError,'workspace_delete_failed'):self.delete(ticket['token'])
  self.assertEqual(self.w.db.execute("SELECT outcome FROM authorization_audit WHERE action='delete_workspace'").fetchone()[0],'failed')
  with self.assertRaisesRegex(WorkerError,'workspace_confirmation_invalid'):self.delete(ticket['token'])
 def test_delete_rechecks_use_and_pending_audit_precedes_docker(self):
  with patch.object(self.w,'exists',return_value=self.volume),patch.object(self.w,'docker',return_value=''):ticket=self.prepare()
  with patch.object(self.w,'exists',return_value=self.volume),patch.object(self.w,'docker',return_value='new-container'):
   with self.assertRaisesRegex(WorkerError,'workspace_in_use'):self.delete(ticket['token'])
  def docker(*args):
   if args[:2]==('volume','rm'):
    self.assertEqual(self.w.db.execute("SELECT outcome FROM authorization_audit WHERE action='delete_workspace'").fetchone()[0],'requested')
   return ''
  with patch.object(self.w,'exists',side_effect=[self.volume,None]),patch.object(self.w,'docker',side_effect=docker):self.delete(ticket['token'])

 def test_unknown_docker_outcome_is_audited(self):
  with patch.object(self.w,'exists',return_value=self.volume),patch.object(self.w,'docker',return_value=''):ticket=self.prepare()
  with patch.object(self.w,'exists',return_value=self.volume),patch.object(self.w,'docker',side_effect=['',WorkerError('docker_unavailable_or_timeout'),WorkerError('docker_unavailable_or_timeout')]):
   with self.assertRaisesRegex(WorkerError,'workspace_delete_unknown'):self.delete(ticket['token'])
  self.assertEqual(self.w.db.execute("SELECT outcome FROM authorization_audit WHERE action='delete_workspace'").fetchone()[0],'unknown')
 def test_audit_is_owner_scoped_in_storage_metadata(self):
  from workspace_storage import describe
  self.w.db.execute('INSERT INTO authorization_audit(actor,action,target,outcome,at) VALUES(?,?,?,?,?)',('member-b','delete_workspace','foreign','deleted',1));self.w.db.commit()
  with patch.object(self.w,'exists',return_value=None),self.w.locked():data=describe(self.w)
  self.assertEqual(data['deletion_history'],[])

 def test_cli_helper_errors_are_sanitized_json(self):
  import subprocess,json
  command=[sys.executable,str(pathlib.Path(__file__).resolve().parent.parent/'scripts/manage_codex_session.py'),
           '--state-dir',self.tmp.name,'--principal','member-a','--role','member',
           'delete-workspace','--confirmation-token','f'*64,'--confirmation','DELETE WORKSPACE']
  result=subprocess.run(command,capture_output=True,text=True,timeout=10)
  self.assertEqual(result.returncode,1)
  self.assertEqual(result.stdout,'')
  self.assertEqual(json.loads(result.stderr),{'error':'workspace_confirmation_invalid'})
 def test_audit_write_failure_prevents_removal(self):
  import sqlite3
  with patch.object(self.w,'exists',return_value=self.volume),patch.object(self.w,'docker',return_value=''):ticket=self.prepare()
  original=self.w.db
  class FailingAudit:
   def __getattr__(self,name):return getattr(original,name)
   def execute(self,query,args=()):
    if query.startswith('INSERT INTO authorization_audit'):raise sqlite3.OperationalError('synthetic unavailable')
    return original.execute(query,args)
  with patch.object(self.w,'db',FailingAudit()),patch.object(self.w,'exists',return_value=self.volume),patch.object(self.w,'docker',return_value='') as docker:
   with self.assertRaisesRegex(WorkerError,'workspace_audit_unavailable'):self.delete(ticket['token'])
   self.assertEqual([c.args for c in docker.call_args_list],[('ps','-aq','--filter','volume='+self.w.volume)])
  self.assertIsNone(original.execute('SELECT used FROM workspace_deletions').fetchone()[0])
 def test_expiry_checked_again_after_idle_inspection(self):
  with patch.object(self.w,'exists',return_value=self.volume),patch.object(self.w,'docker',return_value=''):ticket=self.prepare()
  with patch('workspace_lifecycle.time.time',side_effect=[ticket['expires']-1,ticket['expires']+1]),patch.object(self.w,'exists',return_value=self.volume),patch.object(self.w,'docker',return_value='') as docker:
   with self.assertRaisesRegex(WorkerError,'workspace_confirmation_invalid'):self.delete(ticket['token'])
   self.assertFalse(any(call.args[:2]==('volume','rm') for call in docker.call_args_list))
  self.w.db.execute('UPDATE workspace_deletions SET expires=0');self.w.db.commit()
  with patch.object(self.w,'docker') as docker:
   with self.assertRaisesRegex(WorkerError,'workspace_confirmation_invalid'):self.delete(ticket['token'])
   docker.assert_not_called()

"""Delete only a newly-created synthetic volume in an isolated worker namespace."""
import hashlib,json,pathlib,shutil,sys,tempfile,time
stage=pathlib.Path('/tmp/gvisor-workspace-stage')
sys.path[:0]=[str(stage),str(pathlib.Path.home()/'gvisor-managed-pilot/scripts')]
from manage_codex_session import Worker,WorkerError
from workspace_lifecycle import prepare_deletion,delete_workspace
from workspace_storage import describe
root=pathlib.Path(tempfile.mkdtemp(prefix='poc-deletion-test-'));w=Worker(root,'deletion-test','member');created=False;checks={}
try:
 w.docker('volume','create','--label',w.label,'--label','poc.owner='+hashlib.sha256(w.principal.encode()).hexdigest(),w.volume);created=True
 with w.locked():
  ticket=prepare_deletion(w)
  checks['prepare_retains_volume']=w.exists('volume',w.volume) is not None
  try:delete_workspace(w,ticket['token'],'wrong')
  except WorkerError as exc:checks['wrong_phrase_rejected']=str(exc)=='workspace_confirmation_invalid'
  checks['wrong_phrase_retains_volume']=w.exists('volume',w.volume) is not None
  w.db.execute('INSERT INTO sessions(id,state,created,owner) VALUES(?,?,?,?)',('a'*32,'ready',time.time(),w.principal));w.db.commit()
  try:delete_workspace(w,ticket['token'],'DELETE WORKSPACE')
  except WorkerError as exc:checks['active_session_rejected']=str(exc)=='workspace_in_use'
  w.db.execute("UPDATE sessions SET state='stopped'");w.db.commit()
  result=delete_workspace(w,ticket['token'],'DELETE WORKSPACE')
  checks['volume_removed']=result['deleted'] and w.exists('volume',w.volume) is None;created=False
  try:delete_workspace(w,ticket['token'],'DELETE WORKSPACE')
  except WorkerError as exc:checks['replay_rejected']=str(exc)=='workspace_confirmation_invalid'
  status=describe(w)
  checks['metadata_and_audit']=status['state']=='not_created' and status['deletion_history'][0]['outcome']=='deleted'
finally:
 if created:w.docker('volume','rm',w.volume)
 w.db.close();shutil.rmtree(root)
checks['isolated_state_removed']=True
print(json.dumps({'checks':checks,'passed':all(checks.values()) and len(checks)==8,'user_workspace_deleted':False,'credentials_read':False},indent=2))
raise SystemExit(not all(checks.values()) or len(checks)!=8)

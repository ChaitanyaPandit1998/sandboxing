"""Isolated fixture-only export validation; no user workspace or credentials read."""
import base64,hashlib,io,json,pathlib,shutil,sys,tarfile,tempfile,uuid
stage=pathlib.Path('/tmp/gvisor-workspace-stage')
sys.path[:0]=[str(stage),str(pathlib.Path.home()/'gvisor-managed-pilot/scripts')]
from manage_codex_session import Worker,WorkerError,AGENT,RUNTIME
from workspace_export import export_workspace
root=pathlib.Path(tempfile.mkdtemp(prefix='poc-export-test-'))
w=Worker(root,'export-test','member'); setup='poc-export-fixture-'+uuid.uuid4().hex
checks={};created=False
try:
 with w.locked():
  try:export_workspace(w)
  except WorkerError as exc:checks['missing_not_created']=str(exc)=='workspace_not_found'
 w.docker('volume','create','--label',w.label,'--label','poc.owner='+hashlib.sha256(w.principal.encode()).hexdigest(),w.volume);created=True
 def fixture(code):
  return w.docker('run','--rm','--name',setup,'--pull=never','--runtime='+RUNTIME,'--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--mount','type=volume,source='+w.volume+',target=/workspace','--entrypoint=node',AGENT,'-e',code)
 fixture("const fs=require('fs');fs.writeFileSync('/workspace/fixture.txt','fixture-only');fs.chmodSync('/workspace',0o777);")
 with w.locked():result=export_workspace(w)
 data=base64.b64decode(result['archive_base64'])
 with tarfile.open(fileobj=io.BytesIO(data),mode='r:') as archive:
  checks['fixture_contents_exported']=archive.extractfile('./fixture.txt').read()==b'fixture-only'
 checks['content_unchanged']=fixture("const fs=require('fs');if(fs.readFileSync('/workspace/fixture.txt','utf8')!=='fixture-only')process.exit(1);console.log('ok')")=='ok'
 fixture("require('fs').symlinkSync('/etc','/workspace/unsafe-link')")
 with w.locked():
  try:export_workspace(w)
  except WorkerError as exc:checks['symlink_rejected']=str(exc)=='workspace_export_unsafe_or_incomplete'
 w.db.execute('INSERT INTO sessions(id,state,created,owner) VALUES(?,?,?,?)',('a'*32,'ready',1,w.principal));w.db.commit()
 with w.locked():
  try:export_workspace(w)
  except WorkerError as exc:checks['active_session_blocked']=str(exc)=='workspace_in_use'
 checks['probes_removed']=not w.docker('ps','-aq','--filter','label='+w.label,'--filter','label=poc.purpose=workspace-export')
finally:
 try:w.docker('rm','-f',setup)
 except WorkerError:pass
 if created:w.docker('volume','rm',w.volume)
 w.db.close();shutil.rmtree(root)
checks['isolated_fixture_removed']=True
print(json.dumps({'checks':checks,'passed':all(checks.values()) and len(checks)==7,'user_workspace_read':False,'credentials_read':False},indent=2))
raise SystemExit(not all(checks.values()) or len(checks)!=7)

#!/usr/bin/env python3
"""Disposable legacy-to-quota copy, cutover, rollback and explicit finalization."""
import hashlib,json,pathlib,shutil,subprocess,sys,tempfile
sys.path.insert(0,str(pathlib.Path.home()/'gvisor-managed-pilot/scripts'))
from manage_codex_session import Worker,WorkerError,AGENT,RUNTIME
import workspace_migration as migration
import workspace_quota as quota
from workspace_storage import describe
from workspace_lifecycle import prepare_deletion,delete_workspace


def main():
 if sys.platform!='linux' or __import__('os').uname().nodename!='lima-gvisor-poc':raise SystemExit('Lima only')
 root=pathlib.Path(tempfile.mkdtemp(prefix='poc-migration-test-',dir=pathlib.Path.home()/'.local/state'))
 w=Worker(root,'migration-canary','member');canonical=w.volume;checks={};error=None;cleanup=[];registered=False
 def command(*args):
  p=subprocess.run(args,capture_output=True,text=True,timeout=120)
  if p.returncode:raise RuntimeError('fixture_command_failed:'+pathlib.Path(args[0]).name)
  return p.stdout.strip()
 def act(action,record):
  phrase={'cutover':'MIGRATE WORKSPACE','rollback':'ROLLBACK WORKSPACE','finalize':'DELETE ROLLBACK COPY','discard':'DISCARD STAGED COPY','abort':'ABORT STAGED COPY'}[action]
  with w.locked():return migration.act(w,action,record['id'],phrase)
 def node(sid,code):return w.docker('exec',w.names(sid)['agent'],'node','-e',code)
 try:
  command('sudo','-n',quota.HELPER,'register','--state-dir',str(root));registered=True
  w.docker('volume','create','--label',w.label,'--label','poc.owner='+hashlib.sha256(w.principal.encode()).hexdigest(),canonical)
  w.docker('run','--rm','--pull=never','--runtime='+RUNTIME,'--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--mount','type=volume,source='+canonical+',target=/workspace','--entrypoint=node',AGENT,'-e',"const fs=require('fs');fs.mkdirSync('/workspace/nested');fs.mkdirSync('/workspace/empty');fs.writeFileSync('/workspace/nested/file','migration-fixture',{mode:0o640});fs.linkSync('/workspace/nested/file','/workspace/hardlink');fs.symlinkSync('nested/file','/workspace/link');fs.symlinkSync('/not-read-during-migration','/workspace/external')")
  with w.locked():record=migration.prepare(w)
  # Simulate interruption after a partially copied target, with source untouched.
  backend=pathlib.Path('/var/lib/gvisor-workspace-quota')/(w.namespace+'-'+hashlib.sha256(w.principal.encode()).hexdigest())
  code="import pathlib,json;root=pathlib.Path("+repr(str(backend))+");p=root/'manifest.json';data=json.loads(p.read_text());assert data['owner']=='migration-canary';data['phase']='copying';p.write_text(json.dumps(data));(root/'mount/workspace/hardlink').unlink()"
  command('sudo','-n','python3','-c',code)
  record['phase']='copying';migration.atomic(migration.record_path(w),record)
  act('abort',record)
  checks['interrupted_copy_abort_preserves_original']=w.exists('volume',canonical) is not None and quota.call(w,'status')['state']=='absent' and not quota.enabled(w)
  with w.locked():record=migration.prepare(w)
  checks['verified_copy_prepared']=record['phase']=='prepared' and record['logical_bytes']==17
  checks['original_binding_retained']=w.volume==canonical and not quota.enabled(w) and w.exists('volume',canonical) is not None
  with w.locked():legacy=w.create('legacy-before')['id']
  try:act('cutover',record)
  except WorkerError as exc:checks['active_cutover_blocked']=str(exc)=='workspace_in_use'
  with w.locked():w.stop(legacy)
  act('cutover',record)
  with w.locked():data=describe(w)
  checks['quota_cutover_verified']=w.volume==canonical+'-quota' and data['hard_quota_enforced'] and data['quota_bytes']==quota.LIMIT
  checks['original_volume_preserved']=w.exists('volume',canonical) is not None
  with w.locked():sid=w.create('read-copy')['id']
  node(sid,"const fs=require('fs');if(fs.readFileSync('/workspace/nested/file','utf8')!=='migration-fixture'||fs.statSync('/workspace/hardlink').ino!==fs.statSync('/workspace/nested/file').ino||fs.readlinkSync('/workspace/external')!=='/not-read-during-migration')process.exit(1)")
  checks['copied_files_links_read_in_managed_session']=True
  with w.locked():w.stop(sid)
  try:
   with w.locked():prepare_deletion(w)
  except WorkerError as exc:checks['permanent_deletion_blocked_with_rollback_copy']=str(exc)=='migration_rollback_retained'
  act('rollback',record)
  checks['rollback_restores_original_binding']=w.volume==canonical and not quota.enabled(w) and quota.call(w,'status')['state']=='ready'
  act('cutover',record)
  with w.locked():sid=w.create('new-work')['id']
  node(sid,"require('fs').writeFileSync('/workspace/new-work','keep-new-work')")
  with w.locked():w.stop(sid)
  try:act('rollback',record)
  except WorkerError as exc:checks['new_work_prevents_silent_rollback']=str(exc)=='migration_contents_changed'
  act('finalize',record)
  checks['explicit_finalize_removes_only_legacy_copy']=w.exists('volume',canonical) is None and quota.enabled(w) and migration.read_record(w)['phase']=='finalized'
  with w.locked():sid=w.create('after-finalize')['id']
  node(sid,"if(require('fs').readFileSync('/workspace/new-work','utf8')!=='keep-new-work')process.exit(1)")
  checks['new_work_survives_finalization']=True
  with w.locked():
   w.stop(sid);ticket=prepare_deletion(w);delete_workspace(w,ticket['token'],'DELETE WORKSPACE')
  checks['finalized_workspace_deletion_complete']=quota.call(w,'status')['state']=='absent'
  with w.locked():sid=w.create('fresh-after-delete')['id']
  node(sid,"if(require('fs').existsSync('/workspace/new-work'))process.exit(1)")
  checks['post_migration_recreation_is_empty_quota_workspace']=w.volume==canonical+'-quota' and quota.call(w,'status')['hard_quota_enforced']
  with w.locked():
   w.stop(sid);ticket=prepare_deletion(w);delete_workspace(w,ticket['token'],'DELETE WORKSPACE')
  checks['migration_audit_recorded']=w.db.execute("SELECT COUNT(*) FROM authorization_audit WHERE action LIKE 'migration_%'").fetchone()[0]>=8
  if not all(checks.values()) or len(checks)!=15:raise RuntimeError('migration_acceptance_failed')
 except BaseException as exc:error=str(exc)[:200] or type(exc).__name__
 finally:
  try:
   with w.locked():
    for row in w.visible_rows():w.stop(row['id'])
   record=migration.read_record(w)
   current=quota.call(w,'status')
   if current.get('state')=='ready':
    if record and record['phase'] in ('prepared','rolled_back') and not quota.enabled(w):act('discard',record)
    elif record and record['phase']=='copying':act('abort',record)
    elif record and record['phase']=='active':act('finalize',record)
    if quota.call(w,'status').get('state')=='ready':
     with w.locked():ticket=prepare_deletion(w);delete_workspace(w,ticket['token'],'DELETE WORKSPACE')
   if w.exists('volume',canonical) is not None:w.docker('volume','rm',canonical)
   if registered:command('sudo','-n',quota.HELPER,'unregister',w.namespace)
  except Exception as exc:cleanup.append(str(exc)[:200])
  w.db.close()
  if not cleanup:shutil.rmtree(root)
 checks['fixture_cleaned']=not root.exists() and not cleanup
 print(json.dumps({'checks':checks,'passed':error is None and all(checks.values()),'error':error,'cleanup_errors':cleanup,'actual_workspace_touched':False,'model_requests':0,'namespace':w.namespace},indent=2))
 return 0 if error is None and all(checks.values()) else 1


if __name__=='__main__':raise SystemExit(main())

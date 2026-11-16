#!/usr/bin/env python3
"""Isolated new-owner canary for the installed quota-backed managed worker.
Run inside Lima as the trusted pilot user. No model traffic or user data access.
"""
import base64
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

sys.path.insert(0, str(Path.home()/'gvisor-managed-pilot/scripts'))
from manage_codex_session import Worker, WorkerError
from workspace_storage import describe, checked_volume
from workspace_export import export_workspace
from workspace_lifecycle import prepare_deletion, delete_workspace
import workspace_quota as quota


def main():
    if sys.platform != 'linux' or __import__('os').uname().nodename != 'lima-gvisor-poc':
        raise SystemExit('Only run inside lima-gvisor-poc')
    root = Path(tempfile.mkdtemp(prefix='poc-managed-quota-', dir=Path.home()/'.local/state'))
    owner = 'quota-canary'
    w = Worker(root, owner, 'member')
    checks = {}
    durations = []
    error = None
    cleanup_errors = []
    registered = False
    identity = None
    backend_path = Path('/var/lib/gvisor-workspace-quota')/(w.namespace+'-'+hashlib.sha256(owner.encode()).hexdigest())
    def command(*args):
        result = subprocess.run(args, capture_output=True, text=True, timeout=120)
        if result.returncode:
            raise RuntimeError('canary_command_failed:'+Path(args[0]).name+':'+result.stderr.strip()[:200])
        return result.stdout.strip()
    def execute(sid, *args):
        return subprocess.run(['docker','exec',w.names(sid)['agent'],*args],capture_output=True,text=True,timeout=60)
    def create(key):
        started=time.monotonic()
        with w.locked(): row=w.create(key)
        durations.append(round(time.monotonic()-started,3))
        return row['id']
    try:
        command('sudo','-n',quota.HELPER,'register','--state-dir',str(root));registered=True
        config=root/'quota-owners.json';config.write_text(json.dumps({'owners':[owner]}));config.chmod(0o600)
        first,second=create('first'),create('second')
        checks['two_managed_sessions_ready']=w.get(first)['state']==w.get(second)['state']=='ready'
        checks['same_owner_same_volume']=w.session_volume(first)==w.session_volume(second)==w.volume
        with w.locked(): data=describe(w)
        identity=checked_volume(w)['_quota']['identity']
        checks['verified_hard_quota_metadata']=data['hard_quota_enforced'] and data['quota_bytes']==quota.LIMIT and data['active_sessions']==2
        foreign=Worker(root,'quota-neighbor','member')
        try:
            checks['other_owner_cannot_see_quota_workspace']=quota.call(foreign,'status')['state']=='absent'
            try:quota.call(foreign,'delete',identity)
            except WorkerError as exc:checks['other_owner_cannot_delete_quota_workspace']=str(exc)=='quota_identity_changed'
        finally:foreign.db.close()
        try:
            command('sudo','-n','xfs_quota','-x','-c','limit -p bhard=6g 1',str(backend_path/'mount'))
            try:checked_volume(w)
            except WorkerError as exc:checks['changed_quota_limit_fails_closed']=str(exc)=='quota_limit_mismatch'
        finally:
            command('sudo','-n','xfs_quota','-x','-c','limit -p bhard=5g 1',str(backend_path/'mount'))
        checks['no_host_paths_in_public_metadata']='/var/lib/gvisor-workspace-quota' not in json.dumps(data)
        checks['workspace_shared_only_through_managed_volume']=execute(first,'node','-e',"require('fs').writeFileSync('/workspace/canary.txt','managed-quota-fixture')").returncode==0 and execute(second,'node','-e',"if(require('fs').readFileSync('/workspace/canary.txt','utf8')!=='managed-quota-fixture')process.exit(1)").returncode==0
        a=execute(first,'fallocate','-l',str(3*1024**3),'/workspace/one')
        b=execute(second,'fallocate','-l',str(2*1024**3-8*1024**2),'/workspace/two')
        overflow=execute(second,'fallocate','-l','16777216','/workspace/overflow')
        checks['aggregate_limit_across_sessions']=a.returncode==b.returncode==0 and overflow.returncode!=0 and 'No space left on device' in overflow.stderr
        with w.locked():
            for name,operation in [('active_export_blocked',export_workspace),('active_deletion_blocked',prepare_deletion)]:
                try:operation(w)
                except WorkerError as exc:checks[name]=str(exc)=='workspace_in_use'
        checks['freeing_space_recovers']=execute(first,'node','-e',"const fs=require('fs');for(const n of ['one','two','overflow'])fs.rmSync('/workspace/'+n,{force:true});fs.writeFileSync('/workspace/recovered.txt','ok')").returncode==0
        with w.locked():w.stop(first);w.stop(second)
        with w.locked(): archive=base64.b64decode(export_workspace(w)['archive_base64'])
        with tarfile.open(fileobj=io.BytesIO(archive),mode='r:') as tar:
            checks['readonly_export_matches_fixture']=tar.extractfile('./canary.txt').read()==b'managed-quota-fixture'
        # Drop only disposable Docker metadata, then test service remount recovery.
        w.docker('volume','rm',w.volume)
        command('sudo','-n','umount',str(backend_path/'mount'))
        with w.locked():
            try:describe(w)
            except WorkerError as exc:checks['missing_mount_fails_closed']=str(exc)=='quota_mount_unavailable'
        command('sudo','-n','systemctl','restart','gvisor-workspace-quota.service')
        recovered=create('after-recovery')
        checks['service_recovery_preserves_data']=execute(recovered,'node','-e',"if(require('fs').readFileSync('/workspace/canary.txt','utf8')!=='managed-quota-fixture')process.exit(1)").returncode==0
        with w.locked():
            checks['quota_verified_after_recovery']=describe(w)['hard_quota_enforced']
            w.db.execute('UPDATE sessions SET expires=? WHERE id=?',(time.time()-1,recovered));w.db.commit()
            w.reconcile()
            retained=describe(w)
            checks['expiry_retains_quota_workspace']=(w.get(recovered)['state']=='stopped' and w.get(recovered)['stop_reason']=='expired'
                and retained['state']=='retained' and retained['hard_quota_enforced']
                and w.exists('container',w.names(recovered)['agent']) is None
                and w.exists('container',w.names(recovered)['gateway']) is None)
            ticket=prepare_deletion(w)
            result=delete_workspace(w,ticket['token'],'DELETE WORKSPACE')
            after=describe(w)
        checks['confirmed_deletion_removes_backing_data']=result['deleted'] and after['state']=='not_created' and subprocess.run(['sudo','-n','test','!','-e',str(backend_path)]).returncode==0
        checks['deletion_audit_recorded']=after['deletion_history'][0]['outcome']=='deleted'
        fresh=create('fresh-after-deletion')
        new_identity=checked_volume(w)['_quota']['identity']
        checks['new_workspace_is_empty']=new_identity!=identity and execute(fresh,'node','-e',"if(require('fs').existsSync('/workspace/canary.txt'))process.exit(1)").returncode==0
        with w.locked():w.stop(fresh)
        try:quota.call(w,'delete',identity)
        except WorkerError as exc:checks['old_storage_identity_cannot_delete_replacement']=str(exc)=='quota_identity_changed'
        with w.locked():
            ticket=prepare_deletion(w)
            delete_workspace(w,ticket['token'],'DELETE WORKSPACE')
        if not all(checks.values()) or len(checks)!=21:
            raise RuntimeError('managed_quota_acceptance_check_failed')
    except BaseException as exc:
        error=str(exc)[:300] or type(exc).__name__
    finally:
        try:
            with w.locked():
                for row in w.visible_rows():
                    w.stop(row['id'])
            current=quota.call(w,'status')
            if current.get('state')=='ready':
                with w.locked():
                    ticket=prepare_deletion(w)
                    delete_workspace(w,ticket['token'],'DELETE WORKSPACE')
            if registered:
                command('sudo','-n',quota.HELPER,'unregister',w.namespace)
        except Exception as exc:
            cleanup_errors.append(str(exc)[:200])
        w.db.close()
        if not cleanup_errors:
            shutil.rmtree(root)
    checks['canary_resources_removed']=not root.exists() and not cleanup_errors
    result={'checks':checks,'passed':error is None and all(checks.values()),'create_seconds':durations,
            'error':error,'cleanup_errors':cleanup_errors,'legacy_workspace_migrated':False,
            'model_requests':0,'owner':owner,'namespace':w.namespace}
    print(json.dumps(result,indent=2))
    return 0 if result['passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())

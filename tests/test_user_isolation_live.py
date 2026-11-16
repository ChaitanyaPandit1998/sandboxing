"""Explicit opt-in real HTTP/container ownership checks against an isolated VM state."""
import hashlib
import http.client
import importlib.util
import json
import os
import pathlib
import subprocess
import threading
import unittest
import uuid

ROOT=pathlib.Path(__file__).resolve().parent.parent
spec=importlib.util.spec_from_file_location('ownership_console',ROOT/'scripts/serve_session_console.py')
console=importlib.util.module_from_spec(spec);spec.loader.exec_module(console)


@unittest.skipUnless(os.environ.get('POC_LIVE_OWNERSHIP')=='1','explicit isolated VM test')
class LiveOwnershipTests(unittest.TestCase):
    def test_http_roles_and_persistent_volume_isolation(self):
        home=subprocess.check_output(['limactl','shell','gvisor-poc','--','printenv','HOME'],text=True).strip()
        state=home+'/.local/state/poc-user-test-'+uuid.uuid4().hex
        servers=[];sessions=[];checks={}
        def server(principal,role):
            adapter=console.Adapter(state,principal,role);adapter.command[5]=home+'/gvisor-user-scope-src/scripts/manage_codex_session.py'
            s=console.Server(('127.0.0.1',0),adapter);t=threading.Thread(target=s.serve_forever,daemon=True);t.start()
            client={'server':s,'thread':t,'cookie':None,'csrf':None};servers.append(client)
            status,data=request(client,'/api/bootstrap');self.assertEqual(status,200)
            client['csrf']=data['csrf'];return client
        def request(client,path,body=None,headers=None):
            s=client['server'];h=dict(headers or {})
            if client['cookie']:h.setdefault('Cookie',client['cookie'])
            if body is not None:h.update({'Content-Type':'application/json','Origin':s.origin,'X-POC-CSRF':client['csrf']})
            c=http.client.HTTPConnection('127.0.0.1',s.server_port,timeout=180)
            c.request('POST' if body is not None else 'GET',path,json.dumps(body) if body is not None else None,h)
            r=c.getresponse();status=r.status;data=json.loads(r.read())
            if r.getheader('Set-Cookie'):client['cookie']=r.getheader('Set-Cookie').split(';')[0]
            c.close();return status,data
        def create(client,key):
            status,row=request(client,'/api/sessions',{'policy_id':console.POLICY},{'Idempotency-Key':key})
            self.assertEqual(status,201,row);sessions.append(row['id']);return row
        docker=['limactl','shell','gvisor-poc','--','docker']
        namespace=hashlib.sha256(state.encode()).hexdigest()[:10]
        def name(sid):return f'poc-managed-{namespace}-{sid}-agent'
        def run(*args):return subprocess.check_output([*docker,*args],text=True,stderr=subprocess.STDOUT,timeout=30).strip()
        try:
            a,b,op=server('member-a','member'),server('member-b','member'),server('local-pilot','operator')
            first,other=create(a,'shared-key-123'),create(b,'shared-key-123')
            checks['same_key_scoped_by_owner']=first['id']!=other['id']
            checks['idempotent_owner_retry']=create(a,'shared-key-123')['id']==first['id']
            checks['principal_header_cannot_impersonate']=request(a,'/api/identity',headers={'X-Principal':'member-b','X-Role':'operator'})[1]['principal']=='member-a'
            checks['request_owner_override_rejected']=request(a,'/api/sessions',{'policy_id':console.POLICY,'owner':'member-b'},{'Idempotency-Key':'override-123'})[0]==400
            checks['list_is_owner_scoped']={x['id'] for x in request(a,'/api/sessions')[1]['sessions']}=={first['id']}
            checks['foreign_targets_denied']=all(request(a,'/api/sessions/'+other['id']+suffix)[0]==404 for suffix in ['', '/events','/terminal']) and request(a,'/api/sessions/'+other['id']+'/stop',{})[0]==404
            checks['operator_read_but_no_credential_attach']=request(op,'/api/sessions/'+other['id'])[0]==200 and request(op,'/api/sessions/'+other['id']+'/terminal')[0]==403
            run('exec',name(first['id']),'sh','-c','printf ONLY_A > /workspace/owner-marker; printf TEMP_A > /home/agent/session-marker')
            checks['other_user_cannot_read_workspace_marker']=run('exec',name(other['id']),'sh','-c','test ! -e /workspace/owner-marker && test ! -e /home/agent/session-marker && echo ISOLATED')=='ISOLATED'
            run('exec',name(other['id']),'sh','-c','printf ONLY_B > /workspace/owner-b-marker')
            request(a,'/api/sessions/'+first['id']+'/stop',{})
            replacement=create(a,'replacement-key-123')
            checks['same_user_workspace_persists']=run('exec',name(replacement['id']),'cat','/workspace/owner-marker')=='ONLY_A'
            checks['replacement_home_is_ephemeral']=run('exec',name(replacement['id']),'sh','-c','test ! -e /home/agent/session-marker && echo EPHEMERAL')=='EPHEMERAL'
            checks['replacement_cannot_read_other_workspace']=run('exec',name(replacement['id']),'sh','-c','test ! -e /workspace/owner-b-marker && echo ISOLATED')=='ISOLATED'
            code='import pathlib,sys,time;sys.path.insert(0,str(pathlib.Path.home()/"gvisor-user-scope-src/scripts"));from manage_codex_session import Worker;import security_history as h;w=Worker(sys.argv[1]);[h.record(w.db,s,s,"egress_denied",h.DETAILS["egress_denied"],time.time()) for s in sys.argv[2:]];w.db.commit();h.ingest(w,{})'
            subprocess.run(['limactl','shell','gvisor-poc','--','python3','-c',code,state,replacement['id'],other['id']],capture_output=True,check=True,timeout=30)
            checks['history_is_owner_scoped']=all(e['session_id'] in {first['id'],replacement['id']} for e in request(a,'/api/security-events')[1]['events'])
            a_alerts=request(a,'/api/alerts')[1];b_alerts=request(b,'/api/alerts')[1];foreign=b_alerts['alerts'][0]
            checks['alert_counts_scoped']=a_alerts['counts']['open']==1 and b_alerts['counts']['open']==1
            checks['foreign_alert_action_denied']=request(a,'/api/alerts/'+foreign['id']+'/resolve',{})[0]==404
            request(b,'/api/alerts/'+foreign['id']+'/acknowledge',{})
            checks['audit_is_owner_scoped']=all(e['alert_id']!=foreign['id'] for e in request(a,'/api/alerts')[1]['audit'])
            checks['monitor_is_owner_scoped']=all(e['id'] in {first['id'],replacement['id']} for e in request(a,'/api/monitor')[1]['sessions'])
            expire='import sqlite3,sys,time;c=sqlite3.connect(sys.argv[1]+"/sessions.sqlite");c.execute("UPDATE sessions SET expires=? WHERE id=?",(time.time()-1,sys.argv[2]));c.commit()'
            subprocess.run(['limactl','shell','gvisor-poc','--','python3','-c',expire,state,replacement['id']],capture_output=True,check=True)
            op['server'].adapter.run('reconcile')
            expired=request(a,'/api/sessions/'+replacement['id'])[1]
            checks['operator_expiry_reconciles_member_resources']=expired['state']=='stopped' and expired['stop_reason']=='expired' and request(b,'/api/sessions/'+other['id'])[1]['state']=='ready'
            checks['operator_can_stop_foreign_session']=request(op,'/api/sessions/'+other['id']+'/stop',{})[1]['state']=='stopped'
            self.assertTrue(all(checks.values()),checks)
        finally:
            if servers:
                for sid in set(sessions):
                    servers[-1]['server'].adapter.run('stop',sid)
            for client in servers:
                client['server'].shutdown();client['server'].server_close();client['thread'].join()
            for owner in ['member-a','member-b']:
                volume=f'poc-managed-{namespace}-user-'+hashlib.sha256(owner.encode()).hexdigest()[:16]+'-workspace'
                p=subprocess.run([*docker,'volume','inspect',volume],capture_output=True,text=True)
                if p.returncode==0:
                    labels=json.loads(p.stdout)[0]['Labels'];self.assertEqual(labels['poc.worker'],namespace);self.assertEqual(labels['poc.owner'],hashlib.sha256(owner.encode()).hexdigest());run('volume','rm',volume)
            code='import pathlib,shutil,sys;p=pathlib.Path(sys.argv[1]);assert p.parent==pathlib.Path.home()/".local/state" and p.name.startswith("poc-user-test-");shutil.rmtree(p,ignore_errors=True)'
            subprocess.run(['limactl','shell','gvisor-poc','--','python3','-c',code,state],capture_output=True,check=True)
        checks['isolated_resources_cleaned']=True
        target=os.environ.get('POC_OWNERSHIP_RESULT')
        if target:pathlib.Path(target).write_text(json.dumps({'passed':all(checks.values()),'checks':checks,'scope':'real containers plus three loopback APIs with trusted test principals; no SSO/authenticated end-user claim; no model/login data'},indent=2)+'\n')
        print('OWNERSHIP_CHECKS '+json.dumps(checks),flush=True)


if __name__=='__main__':unittest.main()

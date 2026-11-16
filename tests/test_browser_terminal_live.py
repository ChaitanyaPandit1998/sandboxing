"""Opt-in real VM/HTTP/PTY test. No credentials, device codes or model tasks."""
import base64
import hashlib
import http.client
import json
import os
import pathlib
import subprocess
import sys
import threading
import time
import unittest
import uuid

ROOT=pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'scripts'))
from serve_session_console import Adapter,Server


@unittest.skipUnless(os.environ.get('POC_LIVE_BROWSER_TERMINAL')=='1','explicit isolated VM validation')
class BrowserTerminalLiveTests(unittest.TestCase):
    def test_real_http_codex_attach_disconnect_stop_and_workspace(self):
        tag=uuid.uuid4().hex[:12];state='/home/chaitanya.guest/.local/state/poc-terminal-live-'+tag
        owner='terminal-test-'+tag;adapter=Adapter(state,owner,'member')
        adapter.command[5]='/tmp/gvisor-terminal-stage/scripts/manage_codex_session.py'
        namespace=hashlib.sha256(state.encode()).hexdigest()[:10]
        volume='poc-managed-'+namespace+'-user-'+hashlib.sha256(owner.encode()).hexdigest()[:16]+'-workspace'
        server=Server(('127.0.0.1',0),adapter);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        sid=None;checks={};cookies='';csrf='';channel=None
        def request(path,body=None):
            h={'Cookie':cookies}
            if body is not None:h.update({'Content-Type':'application/json','X-POC-CSRF':csrf,'Origin':server.origin,'Idempotency-Key':'terminal-live-'+tag})
            c=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=120)
            c.request('POST' if body is not None else 'GET',path,json.dumps(body) if body is not None else None,h)
            r=c.getresponse();status,headers,data=r.status,r.getheaders(),json.loads(r.read());c.close()
            return status,headers,data
        def docker(*args):
            return subprocess.check_output(['limactl','shell','gvisor-poc','--','docker',*args],text=True,timeout=30).strip()
        def until(predicate,seconds=15):
            end=time.monotonic()+seconds
            while time.monotonic()<end:
                if predicate():return True
                time.sleep(.1)
            return False
        count_script="const fs=require('fs');let n=0;for(const p of fs.readdirSync('/proc').filter(x=>/^[0-9]+$/.test(x))){try{const a=fs.readFileSync('/proc/'+p+'/cmdline','utf8').split('\\0');if(a.includes('--no-daemon')&&a.some(x=>x.includes('codex')))n++;}catch{}}process.stdout.write(String(n));"
        try:
            status,headers,data=request('/api/bootstrap');self.assertEqual(status,200)
            cookies='; '.join(v.split(';')[0] for k,v in headers if k=='Set-Cookie');csrf=data['csrf']
            status,_,row=request('/api/sessions',{'policy_id':'codex-tls-pilot-v1'});self.assertEqual(status,201)
            sid=row['id'];container='poc-managed-'+namespace+'-'+sid+'-agent'
            checks['isolated_member_session_ready']=row['state']=='ready' and row['owner']==owner
            docker('exec',container,'sh','-c','printf TERMINAL_WORKSPACE_OK > /workspace/terminal-live-marker')
            baseline=int(docker('exec',container,'node','-e',count_script))
            status,_,ticket=request('/api/sessions/'+sid+'/terminal-ticket',{'mode':'attach'});self.assertEqual(status,201)
            status,_,opened=request('/api/terminals',{'ticket':ticket['ticket'],'cols':100,'rows':30});self.assertEqual(status,201)
            cid=opened['id'];channel=server.terminals.channels[cid][0];cursor=0;captured=bytearray()
            start=time.monotonic();saw_cli=False
            while time.monotonic()-start<25:
                status,_,out=request('/api/terminals/'+cid+'?cursor='+str(cursor))
                self.assertEqual(status,200);cursor=out['cursor'];chunk=base64.b64decode(out['data']);captured.extend(chunk)
                if b'\x1b[6n' in chunk:request('/api/terminals/'+cid+'/input',{'data':base64.b64encode(b'\x1b[1;1R').decode()})
                if b'\x1b[c' in chunk:request('/api/terminals/'+cid+'/input',{'data':base64.b64encode(b'\x1b[?1;2c').decode()})
                if b'Codex' in captured or b'Sign in' in captured:saw_cli=True;break
                if out['closed']:break
                time.sleep(.1)
            # Do not retain terminal output or provider authentication material.
            captured.clear();checks['codex_cli_rendered_without_login']=saw_cli;self.assertTrue(saw_cli)
            checks['tracked_remote_wrapper_present']=docker('exec',container,'node','-e',"process.stdout.write(String(require('fs').existsSync('/tmp/.poc-terminal-'+process.argv[1]+'.json')))",channel.relay_id)=='true'
            self.assertTrue(checks['tracked_remote_wrapper_present'])
            status,_,_=request('/api/terminals/'+cid+'/resize',{'cols':110,'rows':32});checks['resize_accepted']=status==200
            status,_,_=request('/api/terminals/'+cid+'/close',{});self.assertEqual(status,200)
            checks['explicit_disconnect_reaped_local_and_remote']=until(lambda:channel.cleanup=='complete',20)
            self.assertTrue(checks['explicit_disconnect_reaped_local_and_remote'])
            checks['codex_process_count_restored']=until(lambda:int(docker('exec',container,'node','-e',count_script))==baseline,10)
            self.assertTrue(checks['codex_process_count_restored'])
            checks['workspace_retained_after_disconnect']=docker('exec',container,'cat','/workspace/terminal-live-marker')=='TERMINAL_WORKSPACE_OK'
            status,_,ticket=request('/api/sessions/'+sid+'/terminal-ticket',{'mode':'attach'})
            status,_,opened=request('/api/terminals',{'ticket':ticket['ticket'],'cols':80,'rows':24});self.assertEqual(status,201)
            early=server.terminals.channels[opened['id']][0]
            request('/api/terminals/'+opened['id']+'/close',{})
            checks['immediate_disconnect_cancelled_startup']=until(lambda:early.cleanup=='complete',20)
            self.assertTrue(checks['immediate_disconnect_cancelled_startup'])
            checks['no_codex_after_immediate_disconnect']=until(lambda:int(docker('exec',container,'node','-e',count_script))==baseline,10)
            self.assertTrue(checks['no_codex_after_immediate_disconnect'])
            status,_,ticket=request('/api/sessions/'+sid+'/terminal-ticket',{'mode':'attach'})
            status,_,opened=request('/api/terminals',{'ticket':ticket['ticket'],'cols':80,'rows':24});self.assertEqual(status,201)
            second=server.terminals.channels[opened['id']][0]
            status,_,_=request('/api/sessions/'+sid+'/stop',{});self.assertEqual(status,200)
            checks['stop_revokes_channel']=second.closed and until(lambda:second.cleanup=='complete',20)
            checks['agent_removed_after_stop']=not docker('ps','-aq','--filter','name=^'+container+'$')
            checks['workspace_volume_retained_after_stop']=docker('volume','inspect',volume,'--format','{{.Name}}')==volume
            self.assertTrue(all(checks.values()),checks)
        finally:
            if sid:
                try:adapter.run('stop',sid)
                except Exception:pass
            server.shutdown();server.server_close();thread.join()
            if volume:
                label=docker('volume','inspect',volume,'--format','{{index .Labels "poc.worker"}}')
                if label==namespace:docker('volume','rm',volume)
            subprocess.run(['limactl','shell','gvisor-poc','--','rm','-rf',state],check=True,timeout=20)
            checks['isolated_state_and_test_volume_removed']=True
            (ROOT/'results/browser-terminal-20261115/live.json').write_text(json.dumps({'checks':checks,'real_provider_login':False,'model_request_made':False,'terminal_transcript_retained':False},indent=2)+'\n')


if __name__=='__main__':unittest.main()

import base64
import http.client
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT=pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'scripts'))
from terminal_relay import TerminalRelay,TerminalError,PtyChannel,dimensions
from serve_session_console import Server,Adapter
from manage_codex_session import Worker,WorkerError
SID='a'*32;OTHER='b'*32;BROWSER='c'*43


class BoundAdapter:
    principal='local-pilot';role='operator'
    def __init__(self):self.ready=True;self.owner=self.principal;self.calls=[];self.expiry=time.time()+3600
    def run(self,action,*args):
        self.calls.append((action,args))
        if action=='close-terminal':return {'closed':True}
        if action in ('authorize-attach','inspect'):return {'id':SID,'state':'ready' if self.ready else 'stopped','owner':self.owner,'expires':self.expiry}
        if action=='reconcile':return {}
        if action=='stop':self.ready=False;return {'state':'stopped'}
        if action=='health':return {'active':True}
        if action=='list':return []
        raise RuntimeError('session_not_found')
    def terminal_command(self,sid,mode,relay):
        # Synthetic terminal: one fixed test program, no user/model/provider traffic.
        return [sys.executable,'-u','-c',"import os,sys,tty; print('PTY_READY:'+str(sys.stdin.isatty())+' ENV_SAFE:'+str('POC_OKTA_CLIENT_SECRET' not in os.environ and 'OPENAI_API_KEY' not in os.environ),flush=True); tty.setraw(0); data=os.read(0,4096); os.write(1,b'ECHO:'+data); import time; time.sleep(30)"]


class FakeChannel:
    count=0
    def __init__(self,adapter,sid,mode,cols,rows,expires):
        type(self).count+=1;self.id=str(type(self).count).zfill(43);self.adapter,self.sid=adapter,sid
        self.closed=False;self.cleanup='not_required';self.buffer=bytearray();self.expires=expires
        self.last_seen=time.monotonic();self.clock=time.monotonic;self.next_check=time.monotonic()+100
    def close(self,reason='disconnected'):
        self.closed=True;self.reason=reason;self.cleanup='complete';self.closed_at=time.monotonic();self.buffer.clear()


class RelayTests(unittest.TestCase):
    def setUp(self):self.now=[time.monotonic()];self.adapter=BoundAdapter();self.relay=TerminalRelay(FakeChannel,lambda:self.now[0])
    def tearDown(self):self.relay.close()
    def ticket(self,mode='attach'):return self.relay.issue(self.adapter,BROWSER,SID,mode)['ticket']
    def test_ticket_expires_is_one_use_and_rechecks_state(self):
        token=self.ticket();self.now[0]+=31
        with self.assertRaises(TerminalError):self.relay.connect(self.adapter,BROWSER,token,80,24)
        token=self.ticket();self.adapter.ready=False
        with self.assertRaisesRegex(TerminalError,'session_not_ready'):self.relay.connect(self.adapter,BROWSER,token,80,24)
        self.adapter.ready=True
        with self.assertRaisesRegex(TerminalError,'terminal_ticket_invalid'):self.relay.connect(self.adapter,BROWSER,token,80,24)
    def test_ticket_and_channel_bound_to_browser_and_principal(self):
        token=self.ticket()
        with self.assertRaises(TerminalError):self.relay.connect(self.adapter,'x'*43,token,80,24)
        token=self.ticket();opened=self.relay.connect(self.adapter,BROWSER,token,80,24)
        with self.assertRaises(TerminalError):self.relay.get(self.adapter,'x'*43,opened['id'])
        self.adapter.principal='foreign-member'
        with self.assertRaises(TerminalError):self.relay.get(self.adapter,BROWSER,opened['id'])
    def test_foreign_owner_even_operator_unknown_mode_command_and_dimensions_denied(self):
        self.adapter.owner='foreign'
        with self.assertRaisesRegex(TerminalError,'attach_owner_required'):self.ticket()
        self.adapter.owner=self.adapter.principal
        for mode in ['shell','attach;whoami',None]:
            with self.assertRaises(TerminalError):self.ticket(mode)
        for cols,rows in [(True,24),(80,0),(301,24),(80,121)]:
            with self.assertRaises(TerminalError):dimensions(cols,rows)
    def test_one_connection_per_session_stop_revokes_ticket_and_channel(self):
        a=self.ticket();b=self.ticket()
        connected=self.relay.connect(self.adapter,BROWSER,a,80,24)
        with self.assertRaisesRegex(TerminalError,'terminal_capacity'):self.relay.connect(self.adapter,BROWSER,b,80,24)
        pending=self.ticket();self.relay.revoke_session(SID)
        self.assertTrue(self.relay.get(self.adapter,BROWSER,connected['id']).closed)
        with self.assertRaises(TerminalError):self.relay.connect(self.adapter,BROWSER,pending,80,24)
    def test_tickets_and_channels_bounded_and_failed_cleanup_retains_capacity(self):
        for _ in range(32):self.ticket()
        with self.assertRaisesRegex(TerminalError,'terminal_capacity'):self.ticket()
        self.now[0]+=31
        token=self.ticket();opened=self.relay.connect(self.adapter,BROWSER,token,80,24)
        ch=self.relay.get(self.adapter,BROWSER,opened['id']);ch.close();ch.cleanup='failed';self.now[0]+=20
        self.relay._prune();self.assertIn(opened['id'],self.relay.channels)
        with self.assertRaisesRegex(TerminalError,'terminal_capacity'):self.relay.connect(self.adapter,BROWSER,self.ticket(),80,24)
    def test_concurrent_connect_reservation_prevents_double_spawn(self):
        entered,release=threading.Event(),threading.Event();created=[]
        def factory(*args):entered.set();release.wait(3);created.append(1);return FakeChannel(*args)
        self.relay.channel_factory=factory
        a,b=self.ticket(),self.ticket();errors=[]
        t=threading.Thread(target=lambda:self.relay.connect(self.adapter,BROWSER,a,80,24));t.start();self.assertTrue(entered.wait(2))
        try:
            with self.assertRaisesRegex(TerminalError,'terminal_capacity'):self.relay.connect(self.adapter,BROWSER,b,80,24)
        finally:release.set();t.join()
        self.assertEqual(len(created),1)
    def test_ssh_transport_disables_host_escape_commands_and_forwarding(self):
        value=subprocess.check_output([str(ROOT/'scripts/terminal_ssh.sh'),'-G','example.invalid'],text=True,stderr=subprocess.DEVNULL)
        options=dict(line.split(' ',1) for line in value.splitlines() if ' ' in line)
        self.assertEqual(options['escapechar'],'none')
        for name in ('enableescapecommandline','permitlocalcommand','forwardagent','forwardx11'):
            self.assertEqual(options[name],'no')
        self.assertEqual(options['clearallforwardings'],'yes')

    def test_command_is_fixed_arguments_no_shell_or_host_secret_environment(self):
        with patch('serve_session_console.subprocess.check_output',return_value='/home/test\n'):
            adapter=Adapter('/state')
        command=adapter.terminal_command(SID,'attach','d'*32)
        self.assertEqual(command[:5],['limactl','--tty=true','shell','gvisor-poc','--'])
        self.assertEqual(command[-4:],['attach',SID,'--terminal-id','d'*32])
        for mode in ['bash','attach;whoami']:
            with self.assertRaises(ValueError):adapter.terminal_command(SID,mode,'d'*32)


class PtyTests(unittest.TestCase):
    def setUp(self):self.adapter=BoundAdapter();self.channel=None
    def tearDown(self):
        if self.channel:
            self.channel.close();self.channel.reader.join(timeout=2)
            deadline=time.monotonic()+4
            while self.channel.cleanup=='pending' and time.monotonic()<deadline:time.sleep(.02)
    def start(self):
        with patch.dict(os.environ,{'POC_OKTA_CLIENT_SECRET':'synthetic-uninherited','OPENAI_API_KEY':'synthetic-uninherited'}):
            self.channel=PtyChannel(self.adapter,SID,'attach',80,24,time.time()+3600)
        return self.channel
    def until(self,predicate):
        limit=time.monotonic()+4
        while time.monotonic()<limit:
            if predicate():return True
            time.sleep(.02)
        return False
    def test_real_pty_input_output_resize_and_cleanup(self):
        ch=self.start();self.assertTrue(self.until(lambda:b'PTY_READY:True' in ch.buffer))
        self.assertIn(b'ENV_SAFE:True',ch.buffer)
        ch.resize(100,30)
        ch.input(base64.b64encode(b'SYNTHETIC_INPUT').decode())
        self.assertTrue(self.until(lambda:b'ECHO:SYNTHETIC_INPUT' in ch.buffer))
        value=ch.output(0);self.assertIn(b'SYNTHETIC_INPUT',base64.b64decode(value['data']))
        ch.close();self.assertTrue(self.until(lambda:ch.cleanup=='complete'))
        self.assertIsNotNone(ch.process.poll());self.assertEqual(ch.buffer,bytearray())
        self.assertTrue(any(action=='close-terminal' for action,_ in self.adapter.calls))
    def test_disconnect_expiry_bounds_and_invalid_input(self):
        ch=self.start()
        for value in ['%%%','a'*5501,'']:
            with self.assertRaises(TerminalError):ch.input(value)
        ch.last_seen=ch.clock()-31
        self.assertTrue(self.until(lambda:ch.closed));self.assertEqual(ch.reason,'disconnected')
    def test_expiry_revokes_real_pty_without_waiting_one_hour(self):
        ch=self.start();ch.expires=time.time()-1
        self.assertTrue(self.until(lambda:ch.closed));self.assertEqual(ch.reason,'expired')
        self.assertTrue(self.until(lambda:ch.cleanup=='complete'))

    def test_buffer_overrun_fails_closed(self):
        ch=self.start();self.assertTrue(self.until(lambda:len(ch.buffer)>0))
        with ch.lock:ch.base=100;ch.buffer=bytearray(b'bounded')
        with self.assertRaisesRegex(TerminalError,'terminal_output_unavailable'):ch.output(0)
        self.assertTrue(ch.closed)


class TerminalHTTPTests(unittest.TestCase):
    def setUp(self):
        self.adapter=BoundAdapter();self.server=Server(('127.0.0.1',0),self.adapter)
        self.server.terminals.channel_factory=FakeChannel
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.cookies='';self.csrf=''
    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join()
    def request(self,path,body=None,headers=None):
        h={'Cookie':self.cookies,**(headers or {})}
        if body is not None:h.update({'Content-Type':'application/json','X-POC-CSRF':self.csrf,'Origin':self.server.origin})
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=10)
        c.request('POST' if body is not None else 'GET',path,json.dumps(body) if body is not None else None,h)
        r=c.getresponse();out=(r.status,r.getheaders(),r.read());c.close();return out
    def bootstrap(self):
        status,headers,data=self.request('/api/bootstrap');self.assertEqual(status,200)
        self.cookies='; '.join(v.split(';')[0] for k,v in headers if k=='Set-Cookie');self.csrf=json.loads(data)['csrf']
    def test_ticket_requires_cookie_csrf_fixed_mode_and_personal_mode(self):
        path='/api/sessions/'+SID+'/terminal-ticket'
        self.assertEqual(self.request(path,{'mode':'attach'})[0],403)
        self.bootstrap();self.assertEqual(self.request(path)[0],405)
        valid=self.csrf;self.csrf='wrong';self.assertEqual(self.request(path,{'mode':'attach'})[0],403);self.csrf=valid
        self.assertEqual(self.request(path,{'mode':'attach','command':'whoami'})[0],400)
        self.assertEqual(self.request(path,{'mode':'shell'})[0],400)
        status,_,data=self.request(path,{'mode':'attach'});self.assertEqual(status,201)
        token=json.loads(data)['ticket'];self.assertNotIn(token,self.server.terminals.tickets)
        status,_,data=self.request('/api/terminals',{'ticket':token,'cols':80,'rows':24});self.assertEqual(status,201)
        self.assertEqual(self.request('/api/terminals',{'ticket':token,'cols':80,'rows':24})[0],400)
    def test_cross_origin_and_foreign_owner_even_operator_rejected(self):
        self.bootstrap();path='/api/sessions/'+SID+'/terminal-ticket'
        self.assertEqual(self.request(path,{'mode':'attach'},headers={'Sec-Fetch-Site':'cross-site'})[0],403)
        self.adapter.owner='foreign';self.assertEqual(self.request(path,{'mode':'attach'})[0],403)
    def test_failed_stop_does_not_revoke_another_channel(self):
        self.bootstrap()
        with patch.object(self.adapter,'run',side_effect=RuntimeError('session_not_found')), patch.object(self.server.terminals,'revoke_session') as revoke:
            self.assertEqual(self.request('/api/sessions/'+SID+'/stop',{})[0],404)
            revoke.assert_not_called()

    def test_local_console_ports_use_distinct_cookie_names(self):
        self.bootstrap()
        self.assertIn('poc_console_'+str(self.server.server_port)+'=',self.cookies)
        self.assertIn('poc_terminal_browser_'+str(self.server.server_port)+'=',self.cookies)
        foreign='poc_console_1='+self.server.secret
        self.assertEqual(self.request('/api/identity',headers={'Cookie':foreign})[0],401)

    def test_static_terminal_assets_have_narrow_csp_and_no_external_scripts(self):
        status,headers,data=self.request('/terminal.html');self.assertEqual(status,200)
        self.assertIn("style-src 'self' 'unsafe-inline'",dict(headers)['Content-Security-Policy'])
        self.assertIn("script-src 'self'",dict(headers)['Content-Security-Policy'])
        self.assertEqual(dict(headers)['X-Frame-Options'],'SAMEORIGIN')
        self.assertNotIn(b'https://',data)
        for path in ['/terminal.js','/vendor/xterm.js','/vendor/addon-fit.js','/vendor/xterm.css']:
            self.assertEqual(self.request(path)[0],200)
        self.assertEqual(dict(self.request('/')[1])['X-Frame-Options'],'DENY')


class WorkerTerminalTests(unittest.TestCase):
    def test_owner_id_and_resource_bound_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            w=Worker(pathlib.Path(tmp)/'state')
            w.db.execute('INSERT INTO sessions(id,request_key,state,created,owner) VALUES(?,?,?,?,?)',(SID,'test','ready',time.time(),'foreign'))
            w.db.commit()
            with patch.object(w,'exists') as inspect:
                with self.assertRaisesRegex(WorkerError,'attach_owner_required'):w.close_terminal(SID,'d'*32)
                inspect.assert_not_called()
            w.db.execute('UPDATE sessions SET owner=? WHERE id=?',('local-pilot',SID));w.db.commit()
            with self.assertRaisesRegex(WorkerError,'invalid_terminal_id'):w.close_terminal(SID,'../unsafe')
            with patch.object(w,'exists',return_value=None):self.assertEqual(w.close_terminal(SID,'d'*32),{'closed':True})
            w.db.close()


if __name__=='__main__':unittest.main()

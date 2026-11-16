"""Signed synthetic OIDC and actual loopback HTTP tests; no external tenant or credentials."""
import base64
import hashlib
import http.client
import json
import os
import pathlib
import sys
import threading
import time
import unittest
from dataclasses import replace
from urllib.parse import parse_qs, urlencode, urlsplit
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from console_auth import AuthProfile, AuthConfigurationError, principal_for_subject
from console_oidc import BrowserAuth, LoginError, OktaProvider
import serve_session_console as console
try:
    from joserfc import jwt
    from joserfc.jwk import RSAKey, KeySet, OctKey
    from authlib.oidc.core import CodeIDToken
    from authlib.integrations.requests_client import OAuth2Session
    import requests
    AVAILABLE = True
except ImportError:
    AVAILABLE = False

PROFILE = AuthProfile('okta', principal='', role='', issuer='https://example.okta.com/oauth2/default',
    client_id='test-client', redirect_uri='http://127.0.0.1:4180/auth/callback',
    client_secret_env='POC_OKTA_CLIENT_SECRET', allowed_subjects=('subject-a', 'subject-b'), operator_subjects=('subject-b',))


class SyntheticProvider(OktaProvider):
    def __init__(self, profile, key):
        self.profile, self.key, self.secret = profile, key, 'synthetic-fixture-only'
        self.jwt_module, self.keyset_class, self.claims_class, self.oauth_class = jwt, KeySet, CodeIDToken, OAuth2Session
        self.metadata = {name: profile.issuer + suffix for name, suffix in (
            ('authorization_endpoint', '/v1/authorize'), ('token_endpoint', '/v1/token'), ('jwks_uri', '/v1/keys'))}
        self.exchanges = []

    def _json(self, url):
        if url != self.metadata['jwks_uri']: raise AssertionError('unexpected_url')
        return {'keys': [self.key.as_dict(private=False)]}

    def token(self, requested_nonce, subject='subject-a', **overrides):
        now = int(time.time())
        claims = {'iss': self.profile.issuer, 'sub': subject, 'aud': self.profile.client_id,
                  'iat': now, 'exp': now + 3600, 'nonce': requested_nonce, **overrides}
        return jwt.encode({'alg': 'RS256', 'kid': self.key.kid}, claims, self.key)

    def exchange(self, code, nonce, verifier):
        self.exchanges.append((code, nonce, verifier))
        if code == 'provider-error': raise LoginError('sso_login_failed')
        return self.validate_token({'id_token': self.token(nonce, code)}, nonce)


@unittest.skipUnless(AVAILABLE, 'install optional requirements-console-oidc.txt')
class OIDCTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = RSAKey.generate_key(2048, parameters={'kid': 'test-key'})

    def setUp(self):
        self.provider = SyntheticProvider(PROFILE, self.key)
        self.current = PROFILE
        self.now = [100.0]
        self.auth = BrowserAuth(PROFILE, self.provider, lambda: self.current, clock=lambda: self.now[0])

    def login(self, subject='subject-a', prior=None):
        browser, url = self.auth.begin()
        state = parse_qs(urlsplit(url).query)['state'][0]
        return self.auth.finish(browser, {'state': state, 'code': subject}, prior)

    def test_authorize_uses_s256_nonce_exact_redirect_and_openid_only(self):
        browser, url = self.auth.begin()
        q = parse_qs(urlsplit(url).query)
        self.assertEqual(q['scope'], ['openid'])
        self.assertEqual(q['response_type'], ['code'])
        self.assertEqual(q['redirect_uri'], [PROFILE.redirect_uri])
        self.assertEqual(q['code_challenge_method'], ['S256'])
        stored = self.auth.pending[browser]
        challenge = base64.urlsafe_b64encode(hashlib.sha256(stored['verifier'].encode()).digest()).decode().rstrip('=')
        self.assertEqual(q['code_challenge'], [challenge])
        self.assertEqual(q['nonce'], [stored['nonce']])
        self.assertNotIn(stored['verifier'], url)
        self.assertNotIn(self.provider.secret, url)
        invalid=self.provider.token('nonce',at_hash='invalid')
        for access in ['', 'wrong-access-token']:
            with self.assertRaises(LoginError):self.provider.validate_token({'id_token':invalid,'access_token':access},'nonce')

    def test_signed_token_success_and_assignment_default_and_operator_roles(self):
        a, b = self.login(), self.login('subject-b')
        sa, sb = self.auth.authenticate(a), self.auth.authenticate(b)
        self.assertEqual(sa['principal'], principal_for_subject(PROFILE.issuer, 'subject-a'))
        self.assertEqual((sa['role'], sb['role']), ('member', 'operator'))
        self.assertNotEqual(sa['csrf'], sb['csrf'])
        self.assertNotEqual(a, b)
        self.assertFalse(any('token' in key for key in sa))

    def test_wrong_issuer_audience_nonce_expiry_azp_and_numeric_dates_rejected(self):
        for change in [{'iss': 'https://attacker.invalid'}, {'aud': 'other'}, {'nonce':'other'},
                       {'exp': int(time.time()) - 100}, {'iat': int(time.time()) + 1000},
                       {'exp': True}, {'at_hash': 'invalid-hash'}, {'azp': 'other'}, {'sub': 'unassigned'}, {'iat': 'yesterday'}]:
            with self.subTest(change=change), self.assertRaises(LoginError):
                self.provider.validate_token({'id_token':self.provider.token('nonce', **change)}, 'nonce')

    def test_invalid_signature_none_and_hmac_algorithms_are_rejected(self):
        alternate = RSAKey.generate_key(2048, parameters={'kid':'test-key'})
        token = self.provider.token('nonce')
        claims = {'iss':PROFILE.issuer,'sub':'subject-a','aud':PROFILE.client_id,'exp':int(time.time())+1000,
                  'iat':int(time.time()),'nonce':'nonce'}
        forged = jwt.encode({'alg':'RS256','kid':'test-key'}, claims, alternate)
        hmac_token = jwt.encode({'alg':'HS256'}, claims, OctKey.import_key(b'x'*32))
        parts = token.split('.')
        none = base64.urlsafe_b64encode(b'{"alg":"none"}').decode().rstrip('=')+'.'+parts[1]+'.'
        for invalid in [forged, hmac_token, none, 'not-jwt', token[:-10]]:
            with self.subTest(kind=invalid[:10]), self.assertRaises(LoginError):
                self.provider.validate_token({'id_token':invalid}, 'nonce')

    def test_missing_required_claims_rejected(self):
        for field in ['iss','sub','aud','iat','exp','nonce']:
            claims = {'iss':PROFILE.issuer,'sub':'subject-a','aud':PROFILE.client_id,'exp':int(time.time())+1000,
                      'iat':int(time.time()),'nonce':'nonce'}
            claims.pop(field)
            token=jwt.encode({'alg':'RS256','kid':'test-key'},claims,self.key)
            with self.subTest(field=field), self.assertRaises(LoginError):
                self.provider.validate_token({'id_token':token},'nonce')

    def test_callback_browser_binding_mismatch_replay_and_expiry(self):
        browser, url = self.auth.begin(); state=parse_qs(urlsplit(url).query)['state'][0]
        with self.assertRaises(LoginError): self.auth.finish('another-browser', {'state':state,'code':'subject-a'})
        self.auth.finish(browser, {'state':state,'code':'subject-a'})
        with self.assertRaises(LoginError): self.auth.finish(browser, {'state':state,'code':'subject-a'})
        browser, url = self.auth.begin()
        with self.assertRaises(LoginError): self.auth.finish(browser, {'state':'\u00e9','code':'subject-a'})
        self.assertNotIn(browser,self.auth.pending)
        browser, url = self.auth.begin();state=parse_qs(urlsplit(url).query)['state'][0]
        self.now[0]+=301
        with self.assertRaises(LoginError): self.auth.finish(browser,{'state':state,'code':'subject-a'})

    def test_provider_error_and_wrong_callback_issuer_consume_transaction(self):
        for extra in [{'error':'access_denied','error_description':'private-detail'}, {'code':'provider-error'},
                      {'iss':'https://attacker.invalid'}, {'unexpected':'value'}]:
            browser,url=self.auth.begin();state=parse_qs(urlsplit(url).query)['state'][0]
            with self.assertRaises(LoginError):self.auth.finish(browser,{'state':state,'code':'subject-a',**extra})
            self.assertNotIn(browser,self.auth.pending)

    def test_rotation_logout_idle_absolute_and_provider_expiry(self):
        a=self.login();b=self.login(prior=a)
        with self.assertRaises(LoginError):self.auth.authenticate(a)
        self.auth.logout(b)
        with self.assertRaises(LoginError):self.auth.authenticate(b)
        a=self.login();self.now[0]+=901
        with self.assertRaises(LoginError):self.auth.authenticate(a)
        a=self.login()
        for _ in range(4):self.now[0]+=800;self.auth.authenticate(a)
        self.now[0]+=401
        with self.assertRaises(LoginError):self.auth.authenticate(a)
        a=self.login();self.auth.sessions[a]['expires']=time.time()-1
        with self.assertRaises(LoginError):self.auth.authenticate(a)

    def test_assignment_reload_revokes_and_role_demotion_applies_next_request(self):
        a=self.login('subject-b')
        self.current=replace(PROFILE,operator_subjects=())
        self.assertEqual(self.auth.authenticate(a)['role'],'member')
        self.current=replace(PROFILE,allowed_subjects=('subject-a',),operator_subjects=())
        with self.assertRaises(LoginError):self.auth.authenticate(a)
        self.assertNotIn(a,self.auth.sessions)
        self.current=PROFILE;a=self.login()
        self.current=replace(PROFILE,client_id='changed')
        with self.assertRaises(LoginError):self.auth.authenticate(a)

    def test_missing_or_bad_config_fails_closed_and_stores_are_bounded(self):
        a=self.login()
        self.auth.profile_loader=lambda: (_ for _ in ()).throw(AuthConfigurationError('config_missing'))
        with self.assertRaises(LoginError):self.auth.authenticate(a)
        self.auth.capacity=1
        self.auth.begin()
        with self.assertRaisesRegex(LoginError,'sso_capacity_reached'):self.auth.begin()
        self.now[0]+=301
        self.auth.begin()  # Old transaction pruned; bounded store is usable again.

    def test_real_authlib_exchange_posts_code_pkce_and_confidential_client_auth(self):
        provider=self.provider;expected={};nonce='expected-nonce'
        class Transport(requests.adapters.BaseAdapter):
            def send(self, request, **kwargs):
                expected.update(body=parse_qs(request.body),auth=request.headers.get('Authorization'),url=request.url)
                response=requests.Response();response.status_code=200
                response._content=json.dumps({'access_token':'synthetic-access','token_type':'Bearer',
                    'id_token':provider.token(nonce)}).encode();response._content_consumed=True;response.request=request;response.url=request.url
                return response
            def close(self):pass
        original=provider._client
        def client():
            value=original();value.mount('https://example.okta.com/',Transport());return value
        with patch.object(provider,'_client',side_effect=client):
            result=OktaProvider.exchange(provider,'synthetic-code',nonce,'v'*43)
        self.assertEqual(result['role'],'member')
        self.assertEqual(expected['body']['code_verifier'],['v'*43])
        self.assertEqual(expected['body']['code'],['synthetic-code'])
        self.assertEqual(expected['body']['redirect_uri'],[PROFILE.redirect_uri])
        self.assertTrue(expected['auth'].startswith('Basic '))
        self.assertEqual(expected['url'],provider.metadata['token_endpoint'])

    def test_metadata_endpoint_and_unavailable_jwks_fail_closed(self):
        for endpoint in ['http://example.okta.com/token','https://attacker.invalid/token',
                         'https://example.okta.com/token?x=1','https://user:pass@example.okta.com/token']:
            with self.assertRaises(LoginError):self.provider._endpoint(endpoint)
        with patch.object(self.provider,'_json',side_effect=OSError('provider-private-error')):
            with self.assertRaisesRegex(LoginError,'^sso_login_failed$'):
                self.provider.validate_token({'id_token':self.provider.token('nonce')},'nonce')


    def test_worker_adapter_clone_is_immutable_and_reuses_only_trusted_base_command(self):
        with patch.object(console.subprocess,'check_output',return_value='/home/test\n') as discover:
            operator=console.Adapter('/private/test-state')
            a=operator.for_identity(principal_for_subject(PROFILE.issuer,'subject-a'),'member')
            b=operator.for_identity(principal_for_subject(PROFILE.issuer,'subject-b'),'operator')
            discover.assert_called_once()
        self.assertEqual(operator.command[operator.command.index('--principal')+1],'local-pilot')
        self.assertNotEqual(a.command,b.command)
        self.assertEqual(a.command[a.command.index('--role')+1],'member')
        self.assertEqual(a.command[-2:],['--state-dir','/private/test-state'])
        self.assertEqual(a.command[:7],operator.command[:7])
        with self.assertRaises(ValueError):operator.for_identity('member;whoami','operator')

    def test_discovery_requires_exact_issuer_safe_endpoints_and_capabilities(self):
        metadata = {**self.provider.metadata, 'issuer': PROFILE.issuer,
                    'response_types_supported':['code'], 'id_token_signing_alg_values_supported':['RS256'],
                    'token_endpoint_auth_methods_supported':['client_secret_basic'], 'code_challenge_methods_supported':['S256']}
        with patch.dict(os.environ, {PROFILE.client_secret_env:'synthetic-fixture-only'}):
            with patch.object(OktaProvider, '_json', return_value=metadata):
                self.assertEqual(OktaProvider(PROFILE).metadata['issuer'], PROFILE.issuer)
            for change in [{'issuer':'https://attacker.invalid'}, {'token_endpoint':'https://attacker.invalid/token'},
                           {'code_challenge_methods_supported':[]}, {'id_token_signing_alg_values_supported':['none']},
                           {'token_endpoint_auth_methods_supported':['none']}]:
                with self.subTest(change=change), patch.object(OktaProvider, '_json',return_value={**metadata,**change}):
                    with self.assertRaisesRegex(AuthConfigurationError, '^oidc_discovery_failed$'):OktaProvider(PROFILE)
            with patch.object(OktaProvider, '_json',side_effect=OSError('sensitive_provider_detail')):
                with self.assertRaisesRegex(AuthConfigurationError, '^oidc_discovery_failed$'):OktaProvider(PROFILE)
        with patch.dict(os.environ,{},clear=True), patch.object(OktaProvider,'_json') as network:
            with self.assertRaisesRegex(AuthConfigurationError,'^okta_client_secret_required$'):OktaProvider(PROFILE)
            network.assert_not_called()

    def test_provider_transport_refuses_redirect_error_and_oversized_body(self):
        class Response:
            def __init__(self,status,parts):self.status_code,self.parts,self.closed=status,parts,False
            def iter_content(self,_):return iter(self.parts)
            def close(self):self.closed=True
        for response in [Response(302,[b'']),Response(504,[b'private error']),Response(200,[b'x'*(1024*1024),b'x'])]:
            with self.assertRaisesRegex(LoginError,'^sso_login_failed$'):OktaProvider._limit_response(response)
        valid=Response(200,[b'{"keys":',b'[]}']);OktaProvider._limit_response(valid)
        self.assertEqual(valid._content,b'{"keys":[]}')


class BoundAdapter:
    def __init__(self, principal='local-pilot',role='operator',calls=None):
        self.principal,self.role,self.calls=principal,role,calls if calls is not None else []
    def for_identity(self,principal,role):return BoundAdapter(principal,role,self.calls)
    def run(self,action,*args):
        self.calls.append((self.principal,self.role,action))
        if action=='reconcile':return {}
        if action=='list':return [{'id':'a'*32,'owner':self.principal}]
        if action=='health':return {'active':True}
        if action=='create':return {'owner':self.principal}
        raise RuntimeError('session_not_found')


@unittest.skipUnless(AVAILABLE,'install optional requirements-console-oidc.txt')
class OIDCHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.key=RSAKey.generate_key(2048,parameters={'kid':'http-test-key'})
    def setUp(self):
        self.provider=SyntheticProvider(PROFILE,self.key)
        self.auth=BrowserAuth(PROFILE,self.provider,lambda:PROFILE)
        self.adapter=BoundAdapter()
        self.server=console.Server(('127.0.0.1',0),self.adapter,auth=self.auth)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
    def request(self,path,cookies='',method='GET',body=None,csrf=None,headers=None):
        h={'Cookie':cookies,**(headers or {})}
        if method=='POST':
            h.update({'Content-Type':'application/json','Origin':self.server.origin})
            if csrf:h['X-POC-CSRF']=csrf
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=10)
        conn.request(method,path,json.dumps(body) if body is not None else None,headers=h)
        res=conn.getresponse();result=(res.status,res.getheaders(),res.read());conn.close();return result
    def login(self,subject='subject-a',prior=''):
        status,headers,_=self.request('/auth/login',prior);self.assertEqual(status,303)
        values=dict(headers);tx=values['Set-Cookie'].split(';')[0]
        self.assertIn('HttpOnly',values['Set-Cookie']);self.assertIn('SameSite=Lax',values['Set-Cookie'])
        state=parse_qs(urlsplit(values['Location']).query)['state'][0]
        path='/auth/callback?'+urlencode({'state':state,'code':subject})
        status,headers,_=self.request(path,tx+('; '+prior if prior else ''),headers={
            'Sec-Fetch-Site':'cross-site','Sec-Fetch-Mode':'navigate','Sec-Fetch-Dest':'document'})
        self.assertEqual(status,303);self.assertEqual(dict(headers)['Location'],'/')
        sid=[v.split(';')[0] for k,v in headers if k=='Set-Cookie' and v.startswith('poc_sso_'+str(self.server.server_port)+'=')][0]
        return sid
    def test_bootstrap_never_grants_local_operator_and_login_page_is_public(self):
        self.assertEqual(self.request('/api/bootstrap')[0],401)
        self.assertEqual(self.request('/api/identity','poc_console='+self.server.secret)[0],401)
        self.assertEqual(self.request('/')[0],303)
        status,headers,data=self.request('/login');self.assertEqual(status,200)
        self.assertIn(b'Continue with Okta',data);self.assertEqual(dict(headers)['Referrer-Policy'],'no-referrer')
        self.assertEqual(self.request('/api/bootstrap',headers={'Origin':'https://attacker.invalid'})[0],403)
    def test_two_browsers_bind_independent_owners_ignore_headers_and_disable_terminal(self):
        a,b=self.login(),self.login('subject-b')
        for cookie,subject,role in [(a,'subject-a','member'),(b,'subject-b','operator')]:
            status,_,raw=self.request('/api/identity',cookie,headers={'X-Role':'operator','X-Principal':'local-pilot'})
            data=json.loads(raw);self.assertEqual(status,200);self.assertEqual(data['principal'],principal_for_subject(PROFILE.issuer,subject))
            self.assertEqual(data['role'],role);self.assertTrue(data['organization_sso'])
            status,_,raw=self.request('/api/sessions',cookie)
            self.assertEqual(status,200);self.assertEqual(json.loads(raw)['sessions'][0]['owner'],data['principal'])
            status,_,raw=self.request('/api/sessions/'+'a'*32+'/terminal',cookie)
            self.assertEqual(status,501);self.assertNotIn(b'limactl',raw)
            csrf=json.loads(self.request('/api/bootstrap',cookie)[2])['csrf']
            self.assertEqual(self.request('/api/sessions/'+'a'*32+'/terminal-ticket',cookie,'POST',{'mode':'attach'},csrf=csrf)[0],501)
        csrf=json.loads(self.request('/api/bootstrap',a)[2])['csrf']
        status,_,raw=self.request('/api/sessions',a,'POST',{'policy_id':console.POLICY},csrf=csrf,
            headers={'Idempotency-Key':'oidc-test-123','X-Principal':'local-pilot','X-Role':'operator'})
        self.assertEqual(status,201)
        self.assertEqual(json.loads(raw)['owner'],principal_for_subject(PROFILE.issuer,'subject-a'))
        self.assertEqual(self.request('/api/sessions',a,'POST',{'policy_id':console.POLICY,'role':'operator'},csrf=csrf)[0],400)
        self.assertEqual((self.adapter.principal,self.adapter.role),('local-pilot','operator'))
    def test_per_browser_csrf_logout_and_session_rotation(self):
        a,b=self.login(),self.login('subject-b')
        status,_,raw=self.request('/api/bootstrap',a);csrf_a=json.loads(raw)['csrf']
        csrf_b=json.loads(self.request('/api/bootstrap',b)[2])['csrf']
        self.assertNotEqual(csrf_a,csrf_b)
        self.assertEqual(self.request('/auth/logout',a,'POST',{},csrf=csrf_b)[0],403)
        self.assertEqual(self.request('/auth/logout',a,'POST',{},csrf=csrf_a,headers={'Sec-Fetch-Site':'cross-site'})[0],403)
        status,headers,_=self.request('/auth/logout',a,'POST',{},csrf=csrf_a)
        self.assertEqual(status,200);self.assertIn('Max-Age=0',dict(headers)['Set-Cookie'])
        self.assertEqual(self.request('/api/identity',a)[0],401)
        self.assertEqual(self.request('/api/identity',b)[0],200)
        c=self.login('subject-b',prior=b)
        self.assertNotEqual(b,c);self.assertEqual(self.request('/api/identity',b)[0],401)
    def test_callback_replay_duplicate_state_and_mismatched_browser_fail_without_echo(self):
        status,headers,_=self.request('/auth/login');h=dict(headers)
        tx=h['Set-Cookie'].split(';')[0];state=parse_qs(urlsplit(h['Location']).query)['state'][0]
        path='/auth/callback?'+urlencode({'code':'private-code','state':state})
        status,headers,raw=self.request(path,'poc_oidc_tx='+'x'*43)
        self.assertEqual(dict(headers)['Location'],'/login?failed=1');self.assertNotIn(b'private-code',raw)
        status,headers,_=self.request(path+'&state=duplicate',tx)
        self.assertEqual(dict(headers)['Location'],'/login?failed=1')
        # Valid transaction, then replay of consumed transaction is denied.
        path='/auth/callback?'+urlencode({'code':'subject-a','state':state})
        self.assertEqual(dict(self.request(path,tx)[1])['Location'],'/')
        self.assertEqual(dict(self.request(path,tx)[1])['Location'],'/login?failed=1')
    def test_shared_adapter_is_never_mutated_by_concurrent_requests(self):
        a,b=self.login(),self.login('subject-b');errors=[]
        def check(cookie,subject):
            for _ in range(8):
                status,_,data=self.request('/api/sessions',cookie)
                if status!=200 or json.loads(data)['sessions'][0]['owner']!=principal_for_subject(PROFILE.issuer,subject):errors.append(subject)
        threads=[threading.Thread(target=check,args=(a,'subject-a')),threading.Thread(target=check,args=(b,'subject-b'))]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertEqual(errors,[])
        self.assertFalse(any(principal=='local-pilot' for principal,_,_ in self.adapter.calls))


if __name__=='__main__':unittest.main()

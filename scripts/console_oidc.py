"""Optional loopback OIDC adapter. Tokens and browser sessions are memory-only."""
import math
import os
import secrets
import threading
import time
from urllib.parse import urlsplit

from console_auth import AuthConfigurationError


class LoginError(RuntimeError):
    """Only bounded, non-secret codes may leave this module."""


def _fail(code='sso_login_failed'):
    raise LoginError(code)


class OktaProvider:
    """Authlib code/PKCE client and RS256 OIDC validation; no implicit flow."""
    def __init__(self, profile):
        try:
            from authlib.integrations.requests_client import OAuth2Session
            from joserfc import jwt
            from joserfc.jwk import KeySet
            from authlib.oidc.core import CodeIDToken
            import requests
        except ImportError:
            raise AuthConfigurationError('oidc_dependencies_required') from None
        secret = os.environ.get(profile.client_secret_env, '')
        if not secret or len(secret) > 4096:
            raise AuthConfigurationError('okta_client_secret_required')
        self.profile, self.secret = profile, secret
        self.oauth_class, self.jwt_module, self.keyset_class, self.claims_class = OAuth2Session, jwt, KeySet, CodeIDToken
        self.http_class = requests.Session
        try:
            metadata = self._json(profile.issuer + '/.well-known/openid-configuration')
            if metadata.get('issuer') != profile.issuer:
                _fail('oidc_metadata_invalid')
            for key in ('authorization_endpoint', 'token_endpoint', 'jwks_uri'):
                self._endpoint(metadata[key])
            if ('code' not in metadata.get('response_types_supported', [])
                    or 'RS256' not in metadata.get('id_token_signing_alg_values_supported', [])
                    or 'client_secret_basic' not in metadata.get('token_endpoint_auth_methods_supported', [])
                    or 'S256' not in metadata.get('code_challenge_methods_supported', [])):
                _fail('oidc_metadata_invalid')
            self.metadata = metadata
        except Exception:
            raise AuthConfigurationError('oidc_discovery_failed') from None

    def _endpoint(self, endpoint):
        u, expected = urlsplit(endpoint), urlsplit(self.profile.issuer)
        if (u.scheme != 'https' or u.netloc != expected.netloc or u.username or u.password
                or u.query or u.fragment or '\\' in endpoint):
            _fail('oidc_metadata_invalid')

    @staticmethod
    def _limit_response(response, *args, **kwargs):
        if response.status_code != 200:
            response.close()
            _fail()
        size, parts = 0, []
        for part in response.iter_content(16384):
            size += len(part)
            if size > 1024 * 1024:
                response.close()
                _fail()
            parts.append(part)
        response._content = b''.join(parts)
        response._content_consumed = True
        return response

    def _json(self, url):
        # A fresh transport per call avoids sharing a mutable cookie jar across logins.
        with self.http_class() as http:
            http.trust_env = False
            with http.get(url, timeout=(3, 10), allow_redirects=False, stream=True) as response:
                self._limit_response(response)
                data = response.json()
                if not isinstance(data, dict):
                    _fail()
                return data

    def _client(self):
        client = self.oauth_class(self.profile.client_id, self.secret, scope='openid',
                                  redirect_uri=self.profile.redirect_uri,
                                  token_endpoint_auth_method='client_secret_basic', code_challenge_method='S256')
        client.trust_env = False
        client.hooks['response'] = [self._limit_response]
        return client

    def authorize(self, state, nonce, verifier):
        with self._client() as client:
            url, _ = client.create_authorization_url(self.metadata['authorization_endpoint'],
                                                     state=state, nonce=nonce, code_verifier=verifier,
                                                     response_mode='query')
            return url

    def exchange(self, code, nonce, verifier):
        try:
            with self._client() as client:
                token = client.fetch_token(self.metadata['token_endpoint'], code=code, code_verifier=verifier,
                                           grant_type='authorization_code', timeout=(3, 10),
                                           allow_redirects=False, stream=True)
            return self.validate_token(token, nonce)
        except Exception:
            raise LoginError('sso_login_failed') from None

    def validate_token(self, token, nonce):
        """Public for signed-token tests; callers receive only bounded identity fields."""
        try:
            if not isinstance(token.get('id_token'), str) or len(token['id_token']) > 65536:
                _fail()
            keys = self._json(self.metadata['jwks_uri'])
            # Algorithm allowlist is fixed, never selected by token headers. No jku/x5u fetches.
            decoded = self.jwt_module.decode(token['id_token'], self.keyset_class.import_key_set(keys), algorithms=['RS256'])
            claims = self.claims_class(decoded.claims, decoded.header,
                options={'iss': {'essential': True, 'value': self.profile.issuer},
                         'aud': {'essential': True, 'value': self.profile.client_id}},
                params={'nonce': nonce, 'client_id': self.profile.client_id,
                        'access_token': token.get('access_token')})
            if 'at_hash' in claims and not (isinstance(token.get('access_token'), str) and token['access_token']):
                _fail()
            claims.validate(leeway=30)
            now = time.time()
            if any(isinstance(claims[k], bool) or not isinstance(claims[k], (int, float))
                   or not math.isfinite(claims[k]) for k in ('iat', 'exp')):
                _fail()
            if claims['exp'] <= now or claims['iat'] > now + 30 or claims['iat'] > claims['exp']:
                _fail()
            identity = self.profile.identity_for_subject(claims['iss'], claims['sub'])
            return {**identity, 'issuer': claims['iss'], 'subject': claims['sub'], 'expires': claims['exp']}
        except Exception:
            raise LoginError('sso_login_failed') from None


class BrowserAuth:
    """Browser-bound one-use transactions and expiring opaque server sessions.

    State is bounded, lock-protected, and lost on restart. No provider tokens retained.
    Assignment/role config is reloaded on every authenticated request.
    """
    transaction_seconds, absolute_seconds, idle_seconds, capacity = 300, 3600, 900, 128

    def __init__(self, profile, provider, profile_loader, clock=time.monotonic, wall=time.time):
        self.profile, self.provider, self.profile_loader = profile, provider, profile_loader
        self.clock, self.wall = clock, wall
        self.pending, self.sessions, self.lock = {}, {}, threading.RLock()

    def _prune(self):
        now = self.clock()
        self.pending = {k: v for k, v in self.pending.items() if v['deadline'] > now}
        self.sessions = {k: v for k, v in self.sessions.items()
                         if min(v['deadline'], v['last_seen'] + self.idle_seconds) > now and v['expires'] > self.wall()}

    def begin(self, previous_transaction=None):
        state, nonce, verifier, browser = (secrets.token_urlsafe(32) for _ in range(4))
        with self.lock:
            self._prune()
            if previous_transaction:
                self.pending.pop(previous_transaction, None)
            if len(self.pending) >= self.capacity:
                _fail('sso_capacity_reached')
            self.pending[browser] = {'state': state, 'nonce': nonce, 'verifier': verifier,
                                     'deadline': self.clock() + self.transaction_seconds}
        try:
            return browser, self.provider.authorize(state, nonce, verifier)
        except Exception:
            with self.lock:
                self.pending.pop(browser, None)
            raise LoginError('sso_login_failed') from None

    def finish(self, browser, query, previous_session=None):
        with self.lock:
            self._prune()
            transaction = self.pending.pop(browser, None)  # Consume before all outcomes/network calls.
        if not transaction or not isinstance(query.get('state'), str) or not secrets.compare_digest(query['state'].encode(), transaction['state'].encode()):
            _fail('sso_transaction_invalid')
        if (set(query) - {'state', 'code', 'iss', 'error', 'error_description'} or query.get('error')
                or not isinstance(query.get('code'), str) or not 0 < len(query['code']) <= 4096
                or ('iss' in query and query['iss'] != self.profile.issuer)):
            _fail('sso_login_failed')
        identity = self.provider.exchange(query['code'], transaction['nonce'], transaction['verifier'])
        try:
            current = self.profile_loader()
            self._same_provider(current)
            mapped = current.identity_for_subject(identity['issuer'], identity['subject'])
        except Exception:
            raise LoginError('sso_assignment_denied') from None
        remaining = identity['expires'] - self.wall()
        if remaining <= 0:
            _fail()
        sid, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with self.lock:
            self._prune()
            if previous_session:
                self.sessions.pop(previous_session, None)
            if len(self.sessions) >= self.capacity:
                _fail('sso_capacity_reached')
            self.sessions[sid] = {**mapped, 'issuer': identity['issuer'], 'subject': identity['subject'],
                                  'expires': identity['expires'], 'csrf': csrf,
                                  'deadline': self.clock() + min(self.absolute_seconds, remaining),
                                  'last_seen': self.clock()}
        return sid

    def _same_provider(self, profile):
        if (profile.mode, profile.issuer, profile.client_id, profile.redirect_uri) != (
                self.profile.mode, self.profile.issuer, self.profile.client_id, self.profile.redirect_uri):
            _fail('sso_configuration_changed')

    def authenticate(self, sid):
        with self.lock:
            self._prune()
            session = self.sessions.get(sid)
            if session is None:
                _fail('sso_session_required')
            try:
                current = self.profile_loader()
                self._same_provider(current)
                mapped = current.identity_for_subject(session['issuer'], session['subject'])
            except Exception:
                self.sessions.pop(sid, None)
                raise LoginError('sso_session_required') from None
            session.update(mapped, last_seen=self.clock())
            return dict(session)

    def logout(self, sid):
        with self.lock:
            self.sessions.pop(sid, None)

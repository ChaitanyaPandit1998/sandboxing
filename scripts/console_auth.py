"""Authentication profiles and stable OIDC ownership mapping.

The optional OIDC adapter is imported only for explicitly selected Okta mode.
Never treat principal_for_subject as authentication or call it on unverified claims.
"""
import hashlib
import json
import pathlib
import re
from dataclasses import dataclass
from urllib.parse import urlsplit


class AuthConfigurationError(ValueError):
    """Bounded error codes only: never echo configuration or credentials."""


def _reject(code):
    raise AuthConfigurationError(code)


def _text(value, maximum=2048):
    return isinstance(value, str) and 0 < len(value) <= maximum and not any(ord(c) < 33 or ord(c) == 127 for c in value)


def _https_issuer(value):
    if not _text(value) or value.endswith('/'):
        return False
    try:
        url = urlsplit(value)
        return (url.scheme == 'https' and bool(url.hostname) and not url.username and not url.password
                and not url.query and not url.fragment and url.port in (None, 443)
                and not any(c in value for c in ('\\', '%'))
                and bool(re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', url.hostname))
                and all(p not in ('.', '..') for p in url.path.split('/')))
    except ValueError:
        return False


def principal_for_subject(issuer, subject):
    """Stable opaque owner ID from an already verified exact issuer/subject pair.

    JSON tuple framing prevents ambiguous concatenation. Email/display names and
    group membership never determine workspace ownership. This performs no auth.
    """
    if not _https_issuer(issuer) or not _text(subject, 255):
        _reject('invalid_identity_mapping')
    pair = json.dumps([issuer, subject], ensure_ascii=True, separators=(',', ':')).encode()
    return 'oidc-' + hashlib.sha256(pair).hexdigest()[:58]


@dataclass(frozen=True)
class AuthProfile:
    mode: str
    principal: str = 'local-pilot'
    role: str = 'operator'
    issuer: str = ''
    client_id: str = ''
    redirect_uri: str = ''
    client_secret_env: str = ''
    allowed_subjects: tuple = ()
    operator_subjects: tuple = ()

    def identity_for_subject(self, issuer, subject):
        """Authorization mapping AFTER external OIDC verification, not token validation."""
        if self.mode != 'okta' or issuer != self.issuer or subject not in self.allowed_subjects:
            _reject('identity_not_assigned')
        return {'principal': principal_for_subject(issuer, subject),
                'role': 'operator' if subject in self.operator_subjects else 'member'}

    def report(self):
        # No client IDs, subjects, secrets, token data, or supplied URLs in diagnostic output.
        return {'mode': self.mode, 'configuration_valid': True,
                'login_ready': self.mode == 'personal', 'organization_sso': False,
                'identity_source': 'trusted_local_binding' if self.mode == 'personal' else 'oidc_pending',
                'status': 'local_only' if self.mode == 'personal' else 'tenant_verification_required',
                'local_fallback': False}

    def require_runnable(self):
        if self.mode == 'okta':
            from console_oidc import OktaProvider
            return OktaProvider(self)
        return None


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _reject('duplicate_auth_configuration_key')
        result[key] = value
    return result


def load_profile(mode='personal', config_path=None, principal=None, role=None, port=4180):
    if mode not in ('personal', 'okta'):
        _reject('invalid_auth_mode')
    if mode == 'personal':
        if config_path is not None:
            _reject('personal_mode_rejects_okta_configuration')
        owner = principal or 'local-pilot'
        selected_role = role or ('member' if principal else 'operator')
        if not re.fullmatch(r'[a-z0-9][a-z0-9._-]{0,63}', owner) or selected_role not in ('member', 'operator'):
            _reject('invalid_local_identity')
        return AuthProfile(mode, principal=owner, role=selected_role)
    if principal is not None or role is not None:
        _reject('okta_mode_rejects_local_identity_override')
    if not config_path:
        _reject('okta_configuration_required')
    try:
        with pathlib.Path(config_path).open('rb') as source:
            raw = source.read(16385)
        if len(raw) > 16384:
            _reject('auth_configuration_too_large')
        data = json.loads(raw, object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError):
        _reject('auth_configuration_unreadable')
    fields = {'issuer', 'client_id', 'redirect_uri', 'client_secret_env', 'allowed_subjects', 'operator_subjects'}
    if not isinstance(data, dict) or set(data) != fields:
        _reject('invalid_auth_configuration_fields')
    if not _https_issuer(data['issuer']):
        _reject('https_issuer_required')
    if not _text(data['client_id'], 255):
        _reject('invalid_client_id')
    if (not isinstance(port, int) or not 1 <= port <= 65535
            or data['redirect_uri'] != f'http://127.0.0.1:{port}/auth/callback'):
        _reject('loopback_callback_must_match_port')
    if not isinstance(data['client_secret_env'], str) or not re.fullmatch(r'POC_OKTA_[A-Z0-9_]{1,64}', data['client_secret_env']):
        _reject('invalid_secret_environment_name')
    for field in ('allowed_subjects', 'operator_subjects'):
        values = data[field]
        if (not isinstance(values, list) or len(values) > 100
                or any(not _text(v, 255) for v in values) or len(set(values)) != len(values)):
            _reject('invalid_subject_assignments')
    if not data['allowed_subjects']:
        _reject('explicit_subject_assignment_required')
    if not set(data['operator_subjects']).issubset(data['allowed_subjects']):
        _reject('operators_must_be_assigned')
    return AuthProfile(mode, principal='', role='', issuer=data['issuer'], client_id=data['client_id'],
                       redirect_uri=data['redirect_uri'], client_secret_env=data['client_secret_env'],
                       allowed_subjects=tuple(data['allowed_subjects']), operator_subjects=tuple(data['operator_subjects']))

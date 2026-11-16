"""Offline auth-profile gates; these do not establish an Okta login."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from console_auth import AuthConfigurationError, load_profile, principal_for_subject
import serve_session_console as console


class AuthProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = pathlib.Path(self.temp.name) / 'auth.json'
        self.data = {'issuer': 'https://example.okta.com/oauth2/default', 'client_id': 'public-client',
                     'redirect_uri': 'http://127.0.0.1:4180/auth/callback',
                     'client_secret_env': 'POC_OKTA_CLIENT_SECRET',
                     'allowed_subjects': ['subject-a', 'subject-b'], 'operator_subjects': ['subject-b']}

    def tearDown(self):
        self.temp.cleanup()

    def profile(self, **overrides):
        data = {**self.data, **overrides}
        self.path.write_text(json.dumps(data))
        return load_profile('okta', str(self.path))

    def test_personal_preserves_legacy_and_explicit_member_defaults(self):
        self.assertEqual((load_profile().principal, load_profile().role), ('local-pilot', 'operator'))
        self.assertEqual(load_profile(principal='member-a').role, 'member')
        self.assertEqual(load_profile(principal='member-a', role='operator').role, 'operator')
        load_profile().require_runnable()
        self.assertFalse(load_profile().report()['organization_sso'])

    def test_modes_cannot_mix_or_fall_back(self):
        for args in [('other',), ('okta',), ('personal', str(self.path)),
                     ('okta', str(self.path), 'local-pilot'), ('okta', str(self.path), None, 'operator')]:
            with self.subTest(args=args), self.assertRaises(AuthConfigurationError):
                load_profile(*args)
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(AuthConfigurationError):
            self.profile().require_runnable()

    def test_issuer_is_exact_https_and_has_no_ambiguous_parts(self):
        for issuer in ['http://example.okta.com', 'https://user:secret@example.okta.com',
                       'https://example.okta.com/', 'https://example.okta.com/x?next=y',
                       'https://example.okta.com/#x', 'https://example.okta.com:9999',
                       'https://example.okta.com/../evil', 'https://example.okta.com/%2e',
                       'https://example.okta.com\\evil', 'https://example.okta.com\n']:
            with self.subTest(issuer=issuer), self.assertRaises(AuthConfigurationError):
                self.profile(issuer=issuer)

    def test_callback_must_match_fixed_loopback_route_and_port(self):
        for uri in ['https://attacker.invalid/auth/callback', 'http://localhost:4180/auth/callback',
                    'http://127.0.0.1:4181/auth/callback', 'http://127.0.0.1:4180/auth/callback?x=1']:
            with self.subTest(uri=uri), self.assertRaises(AuthConfigurationError):
                self.profile(redirect_uri=uri)
        self.path.write_text(json.dumps({**self.data, 'redirect_uri':'http://127.0.0.1:4190/auth/callback'}))
        self.assertTrue(load_profile('okta', str(self.path), port=4190).report()['configuration_valid'])

    def test_only_secret_reference_allowed(self):
        self.profile()
        self.path.write_text(json.dumps({**self.data, 'client_secret': 'do-not-accept'}))
        with self.assertRaisesRegex(AuthConfigurationError, 'invalid_auth_configuration_fields'):
            load_profile('okta', str(self.path))
        for value in ['PATH', 'POC_OKTA_SECRET\n', '', None]:
            with self.subTest(value=value), self.assertRaises(AuthConfigurationError):
                self.profile(client_secret_env=value)

    def test_assignments_are_explicit_bounded_unique_and_least_privilege(self):
        for values in [[], ['*'], ['a'] * 2, [None], ['a b'], [str(i) for i in range(101)]]:
            # Literal '*' is an exact subject, never a wildcard; it cannot grant subject-a.
            if values == ['*']:
                p = self.profile(allowed_subjects=values, operator_subjects=[])
                with self.assertRaises(AuthConfigurationError): p.identity_for_subject(p.issuer, 'subject-a')
                continue
            with self.subTest(values=values), self.assertRaises(AuthConfigurationError):
                self.profile(allowed_subjects=values, operator_subjects=[])
        with self.assertRaisesRegex(AuthConfigurationError, 'operators_must_be_assigned'):
            self.profile(operator_subjects=['unassigned'])

    def test_mapping_separates_issuer_and_subject_and_preserves_case(self):
        issuer = self.data['issuer']
        owner = principal_for_subject(issuer, 'subject-a')
        self.assertEqual(owner, principal_for_subject(issuer, 'subject-a'))
        self.assertRegex(owner, r'^oidc-[a-f0-9]{58}$')
        self.assertNotEqual(owner, principal_for_subject('https://another.okta.com', 'subject-a'))
        self.assertNotEqual(owner, principal_for_subject(issuer, 'Subject-a'))
        self.assertNotEqual(owner, 'local-pilot')
        self.assertNotIn('subject-a', owner)

    def test_authorization_rejects_other_issuer_unassigned_and_local_identity(self):
        p = self.profile()
        self.assertEqual(p.identity_for_subject(p.issuer, 'subject-a')['role'], 'member')
        self.assertEqual(p.identity_for_subject(p.issuer, 'subject-b')['role'], 'operator')
        for issuer, sub in [('https://another.okta.com', 'subject-a'), (p.issuer, 'unassigned')]:
            with self.assertRaisesRegex(AuthConfigurationError, 'identity_not_assigned'):
                p.identity_for_subject(issuer, sub)
        with self.assertRaises(AuthConfigurationError):
            load_profile().identity_for_subject(p.issuer, 'subject-a')

    def test_bad_files_duplicate_keys_unknown_fields_and_size_fail_closed(self):
        for raw in ['{', '[]', '{"issuer":"one","issuer":"two"}', 'x' * 16385,
                    json.dumps({**self.data, 'fallback': True}), '[' * 2000]:
            self.path.write_text(raw)
            with self.subTest(raw=raw[:20]), self.assertRaises(AuthConfigurationError):
                load_profile('okta', str(self.path))

    def test_diagnostics_do_not_disclose_configuration(self):
        report = json.dumps(self.profile().report())
        for value in [self.data['issuer'], 'public-client', 'subject-a', 'POC_OKTA_CLIENT_SECRET']:
            self.assertNotIn(value, report)
        self.assertFalse(self.profile().report()['login_ready'])
        self.assertFalse(self.profile().report()['local_fallback'])

    def test_cli_check_and_okta_gate_run_before_adapter_or_server(self):
        self.profile()
        with patch.dict(os.environ, {}, clear=True), patch.object(console, 'Adapter') as adapter, patch.object(console, 'Server') as server:
            with patch.object(sys, 'argv', ['console', '--check-auth-config']), patch('builtins.print'):
                self.assertEqual(console.main(), 0)
            with patch.object(sys, 'argv', ['console', '--auth-mode', 'okta', '--auth-config', str(self.path), '--check-auth-config']), patch('builtins.print'):
                self.assertEqual(console.main(), 0)
            with patch.object(sys, 'argv', ['console', '--auth-mode', 'okta', '--auth-config', str(self.path)]), patch('builtins.print'):
                self.assertEqual(console.main(), 2)
            adapter.assert_not_called()
            server.assert_not_called()

    def test_actual_cli_preflight_and_gate(self):
        self.profile()
        cmd = [sys.executable, str(ROOT / 'scripts/serve_session_console.py'), '--auth-mode', 'okta', '--auth-config', str(self.path)]
        checked = subprocess.run([*cmd, '--check-auth-config'], capture_output=True, text=True, timeout=10)
        self.assertEqual(checked.returncode, 0)
        self.assertFalse(json.loads(checked.stdout)['login_ready'])
        gated = subprocess.run(cmd, capture_output=True, text=True, timeout=10, env={k:v for k,v in os.environ.items() if not k.startswith('POC_OKTA_')})
        self.assertEqual(gated.returncode, 2)
        self.assertIn(json.loads(gated.stderr)['error'], ('oidc_dependencies_required', 'okta_client_secret_required'))
        self.assertEqual(gated.stdout, '')


if __name__ == '__main__':
    unittest.main()

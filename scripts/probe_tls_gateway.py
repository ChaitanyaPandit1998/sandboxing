#!/usr/bin/env python3
"""Synthetic unauthenticated gateway checks; never reads credentials."""
import json
import os
import socket
import ssl

proxy = os.environ['GATEWAY_IP']
checks = {}


def request(connect='example.com:443', sni='example.com', host='example.com', extra='', trust=True, tls=True, path='/', connect_host=None):
    with socket.create_connection((proxy, 3128), timeout=15) as client:
        client.sendall(f'CONNECT {connect} HTTP/1.1\r\nHost: {connect_host or connect}\r\n\r\n'.encode())
        header = b''
        while b'\r\n\r\n' not in header:
            chunk = client.recv(1)
            if not chunk:
                raise OSError('CONNECT closed')
            header += chunk
        code = int(header.split()[1])
        if code != 200:
            return code
        context = ssl.create_default_context(cafile='/test/ca.pem' if trust else None)
        if sni is None:
            context.check_hostname = False
        stream = context.wrap_socket(client, server_hostname=sni) if tls else client
        with stream:
            stream.sendall(f'GET {path} HTTP/1.1\r\nHost: {host}\r\n{extra}Connection: close\r\n\r\n'.encode())
            response = stream.recv(4096)
            return int(response.split()[1])


def check(name, expected, expected_exception=None, **kwargs):
    try:
        code = request(**kwargs)
        checks[name] = {'passed': code in expected, 'http_status': code}
    except (OSError, ssl.SSLError, ValueError, IndexError) as exc:
        checks[name] = {'passed': 0 in expected and (expected_exception is None or isinstance(exc, expected_exception)), 'exception': type(exc).__name__}


check('approved_https', {200})
check('mismatched_sni', {403, 0}, sni='example.org', host='example.org')
check('encrypted_host_mismatch', {403}, host='example.org')
check('connect_host_mismatch', {403}, connect_host='example.org:443')
check('unlisted_connect', {403}, connect='example.org:443')
check('ip_literal', {403}, connect='1.1.1.1:443')
check('alternate_port', {403}, connect='example.com:8443')
check('metadata_destination', {403}, connect='169.254.169.254:443')
check('missing_sni', {403, 0}, sni=None)
check('plaintext_in_connect', {400, 403, 0}, tls=False)
check('duplicate_host', {400, 403, 0}, extra='Host: example.org\r\n')
check('upgrade_denied', {403}, extra='Upgrade: websocket\r\n')
check('host_port_mismatch', {403}, host='example.com:8443')
check('untrusted_ca', {0}, trust=False, expected_exception=ssl.SSLCertVerificationError)
# API endpoint has no provider credentials: a 401 demonstrates verified upstream TLS reachability.
check('provider_without_credentials', {401}, connect='api.openai.com:443', sni='api.openai.com', host='api.openai.com', path='/v1/models')
try:
    with socket.create_connection(('1.1.1.1', 443), timeout=2):
        checks['direct_egress'] = {'passed': False}
except OSError:
    checks['direct_egress'] = {'passed': True}
print(json.dumps({'passed': all(x['passed'] for x in checks.values()), 'checks': checks}, indent=2))
raise SystemExit(0 if all(x['passed'] for x in checks.values()) else 1)

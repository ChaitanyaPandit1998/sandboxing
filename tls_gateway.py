"""Experimental mitmproxy addon: authorize CONNECT, TLS SNI, and HTTP authority.

Run only with lazy upstream connection establishment, upstream_cert=false,
rawtcp=false, http2=false, and upstream certificate validation enabled.
"""
import asyncio
import ipaddress
import json
import os
import re
import socket
from mitmproxy import ctx, exceptions, http


def hostname(value):
    value = value.lower().rstrip('.')
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', value):
        raise ValueError('invalid hostname')
    if any(not label or len(label) > 63 or label.startswith('-') or label.endswith('-') for label in value.split('.')):
        raise ValueError('invalid label')
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return value
    raise ValueError('IP literals prohibited')


class Gateway:
    def __init__(self):
        self.allowed = {hostname(x.strip()) for x in os.environ.get('POC_ALLOWED_HOSTS', 'example.com').split(',')}
        self.tunnels = {}

    def configure(self, updated):
        if (ctx.options.connection_strategy != 'lazy' or ctx.options.upstream_cert
                or ctx.options.rawtcp or ctx.options.http2 or ctx.options.ssl_insecure
                or not ctx.options.validate_inbound_headers):
            raise exceptions.OptionsError('gateway requires lazy, no upstream sniff/raw TCP/HTTP2, verified TLS and header validation')

    def decision(self, flow, allowed, reason):
        # Deliberately exclude URL paths, headers, bodies, and user input.
        print(json.dumps({'event': 'tls_policy', 'flow_id': flow.id,
                          'decision': 'allow' if allowed else 'deny', 'reason': reason}), flush=True)
        if not allowed:
            flow.response = http.Response.make(403, b'egress policy denied\n', {'Content-Type': 'text/plain'})

    def http_connect(self, flow):
        try:
            host = hostname(flow.request.host)
            headers = flow.request.headers.get_all('host')
            authority = headers[0].lower() if len(headers) == 1 else ''
            allowed = (host in self.allowed and flow.request.port == 443
                       and authority in {host, host + ':443'})
        except ValueError:
            allowed = False
        if allowed:
            self.tunnels[flow.client_conn.id] = host
        self.decision(flow, allowed, 'connect_authority')

    def requestheaders(self, flow):
        target = self.tunnels.get(flow.client_conn.id)
        try:
            sni = hostname(flow.client_conn.sni or '')
            host = hostname(flow.request.host)
            headers = flow.request.headers.get_all('host')
            if len(headers) != 1:
                raise ValueError('one Host required')
            authority = headers[0].lower()
            if authority.endswith(':443'):
                authority = authority[:-4]
            authority = hostname(authority)
            allowed = (flow.client_conn.tls and flow.request.scheme == 'https'
                       and target == sni == host == authority and target in self.allowed
                       and flow.request.port == 443 and flow.request.method != 'CONNECT'
                       and not flow.request.headers.get('upgrade'))
        except ValueError:
            allowed = False
        self.decision(flow, allowed, 'connect_tls_http_match')
        if allowed:
            flow.server_conn.sni = target
            flow.request.stream = True

    def responseheaders(self, flow):
        # Preserve streaming provider responses without retaining response bodies.
        flow.response.stream = True

    async def server_connect(self, data):
        # Resolve once and pin the validated IP; TLS still verifies the original SNI.
        try:
            host, port = data.server.address
            host = hostname(host)
            if host not in self.allowed or port != 443 or data.server.sni != host:
                raise ValueError('unauthorized upstream')
            records = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
            addresses = [row[4][0] for row in records]
            if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
                raise ValueError('non-public DNS answer')
            data.server.address = (addresses[0], port)
        except (ValueError, OSError):
            data.server.error = 'egress upstream policy denied'

    def tcp_start(self, flow):
        flow.kill()

    def client_disconnected(self, client):
        self.tunnels.pop(client.id, None)


addons = [Gateway()]

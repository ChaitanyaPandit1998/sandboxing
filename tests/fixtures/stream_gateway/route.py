"""TEST ONLY: route one synthetic hostname to a loopback TLS fixture.

This replaces production DNS/public-IP routing, so these tests do not validate it.
The fixture container has only an internal Docker network and no real provider access.
"""
from tls_gateway import Gateway


class FixtureGateway(Gateway):
    async def server_connect(self, data):
        if data.server.address == ('fixture.test', 443) and data.server.sni == 'fixture.test':
            data.server.address = ('127.0.0.1', 9443)
        else:
            data.server.error = 'fixture upstream denied'


addons = [FixtureGateway()]

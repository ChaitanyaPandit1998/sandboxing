"""Synthetic TLS/SSE backend and supervised gateway; no model or credential access."""
import datetime
import pathlib
import ssl
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from mitmproxy.certs import CertStore

root = pathlib.Path('/tmp/ca')
CertStore.from_store(root, 'mitmproxy', 2048)
material = (root / 'mitmproxy-ca.pem').read_bytes()
ca_key = serialization.load_pem_private_key(material, password=None)
ca_cert = x509.load_pem_x509_certificate(material)
key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
now = datetime.datetime.now(datetime.timezone.utc)
cert = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'fixture.test')]))
        .issuer_name(ca_cert.subject).public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1)).not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName('fixture.test')]), critical=False)
        .sign(ca_key, hashes.SHA256()))
leaf_key = root / 'fixture-key.pem'
leaf_key.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
leaf_key.chmod(0o600)
(root / 'fixture-cert.pem').write_bytes(cert.public_bytes(serialization.Encoding.PEM))


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *_args):
        pass

    def do_GET(self):
        if self.path == '/reset':
            self.close_connection = True
            return
        if self.path == '/503':
            self.send_response(503)
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Transfer-Encoding', 'chunked')
        self.end_headers()
        try:
            count = 100 if self.path == '/slow' else 2
            for i in range(count):
                data = f'data: event-{i}\n\n'.encode()
                self.wfile.write(f'{len(data):x}\r\n'.encode() + data + b'\r\n')
                self.wfile.flush()
                if self.path == '/truncate':
                    self.close_connection = True
                    return
                time.sleep(2 if self.path == '/stall' else 0.2)
            data = b'data: [DONE]\n\n'
            self.wfile.write(f'{len(data):x}\r\n'.encode() + data + b'\r\n0\r\n\r\n')
            self.wfile.flush()
        except (OSError, ssl.SSLError):
            pass
        self.close_connection = True


server = ThreadingHTTPServer(('127.0.0.1', 9443), Handler)
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain(root / 'fixture-cert.pem', leaf_key)
server.socket = context.wrap_socket(server.socket, server_side=True)
threading.Thread(target=server.serve_forever, daemon=True).start()
args = ['mitmdump', '-q', '--listen-port', '3128', '--set', 'confdir=/tmp/ca',
        '--set', 'ssl_verify_upstream_trusted_ca=/tmp/ca/mitmproxy-ca-cert.pem',
        '--set', 'connection_strategy=lazy', '--set', 'upstream_cert=false',
        '--set', 'rawtcp=false', '--set', 'http2=false', '--set', 'ssl_insecure=false',
        '--set', 'validate_inbound_headers=true', '-s', '/fixture/route.py']
while True:
    child = subprocess.Popen(args)
    pathlib.Path('/tmp/gateway.pid').write_text(str(child.pid))
    child.wait()
    time.sleep(0.2)

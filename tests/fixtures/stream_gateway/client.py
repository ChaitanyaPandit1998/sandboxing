import http.client
import json
import os
import pathlib
import socket
import ssl
import sys
import time


def read(path, cancel=False, timeout=0.8, ready=False):
    begin = time.monotonic()
    row = {'status': None, 'done': False, 'events': [], 'error': None}
    try:
        with socket.create_connection((os.environ['GATEWAY_IP'], 3128), timeout=timeout) as sock:
            sock.sendall(b'CONNECT fixture.test:443 HTTP/1.1\r\nHost: fixture.test:443\r\n\r\n')
            header = b''
            while not header.endswith(b'\r\n\r\n'):
                b = sock.recv(1)
                if not b:
                    raise OSError('closed CONNECT')
                header += b
            if int(header.split()[1]) != 200:
                raise OSError('CONNECT failed')
            context = ssl.create_default_context(cafile='/trust/ca.pem')
            with context.wrap_socket(sock, server_hostname='fixture.test') as stream:
                stream.sendall(f'GET {path} HTTP/1.1\r\nHost: fixture.test\r\nConnection: close\r\n\r\n'.encode())
                response = http.client.HTTPResponse(stream)
                response.begin()
                row['status'] = response.status
                while True:
                    line = response.readline()
                    if not line:
                        break
                    if line.startswith(b'data:'):
                        row['events'].append(round(time.monotonic() - begin, 3))
                        if ready:
                            pathlib.Path('/tmp/first-event').touch()
                        if b'[DONE]' in line:
                            row['done'] = True
                        if cancel:
                            break
    except (OSError, http.client.HTTPException) as exc:
        row['error'] = type(exc).__name__
    return row


mode = sys.argv[1]
if mode == 'suite':
    rows = {name: read(path, cancel=cancel) for name, path, cancel in [
        ('normal', '/normal', False), ('truncated', '/truncate', False),
        ('stalled', '/stall', False), ('client_cancel', '/slow', True),
        ('after_client_cancel', '/normal', False), ('reset', '/reset', False),
        ('provider_503', '/503', False)]}
    normal = rows['normal']
    checks = {
        'progressive_stream': normal['done'] and len(normal['events']) == 3 and normal['events'][-1] - normal['events'][0] >= 0.3,
        'truncated_not_complete': bool(rows['truncated']['events']) and not rows['truncated']['done'],
        'stall_timeout': bool(rows['stalled']['events']) and not rows['stalled']['done'] and rows['stalled']['error'] == 'TimeoutError',
        'client_cancel': len(rows['client_cancel']['events']) == 1 and not rows['client_cancel']['done'],
        'recovery_after_cancel': rows['after_client_cancel']['done'],
        'upstream_reset_detected': (rows['reset']['error'] is not None or rows['reset']['status'] == 502) and not rows['reset']['done'],
        'provider_503_preserved': rows['provider_503']['status'] == 503,
    }
    print(json.dumps({'passed': all(checks.values()), 'checks': checks, 'observations': rows}))
    sys.exit(0 if all(checks.values()) else 1)
else:
    print(json.dumps(read('/slow' if mode == 'interrupt' else '/normal', ready=mode == 'interrupt')))

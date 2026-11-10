#!/usr/bin/env python3
"""Small POC HTTPS CONNECT proxy with an exact-host allowlist."""

import ipaddress
import json
import os
import select
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


ALLOWLIST = {
    name.strip().lower().rstrip(".")
    for name in os.environ.get("POC_ALLOWED_HOSTS", "example.com").split(",")
    if name.strip()
}
LISTEN = ("0.0.0.0", 3128)


def log(decision, host, port, reason=""):
    print(json.dumps({"decision": decision, "host": host, "port": port, "reason": reason}), flush=True)


def connect_public(host, port):
    """Resolve once, reject non-global targets, and connect to the validated IP."""
    last_error = None
    for family, socktype, proto, _canonname, sockaddr in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM):
        try:
            address = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            continue
        if not address.is_global:
            last_error = f"non-public address rejected: {address}"
            continue
        upstream = socket.socket(family, socktype, proto)
        upstream.settimeout(8)
        try:
            upstream.connect(sockaddr)
            upstream.settimeout(None)
            return upstream
        except OSError as exc:
            last_error = str(exc)
            upstream.close()
    raise OSError(last_error or "no public address available")


class ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args):
        pass

    def do_CONNECT(self):
        authority = self.path
        if authority.count(":") != 1:
            log("deny", authority, 0, "invalid authority")
            self.send_error(403, "domain not allowed")
            return
        host, port_text = authority.rsplit(":", 1)
        host = host.lower().rstrip(".")
        try:
            port = int(port_text)
        except ValueError:
            port = 0

        if host not in ALLOWLIST or port != 443:
            log("deny", host, port, "not in exact host/port allowlist")
            self.send_error(403, "domain or port not allowed")
            return

        try:
            upstream = connect_public(host, port)
        except OSError as exc:
            log("error", host, port, str(exc))
            self.send_error(502, "upstream unavailable")
            return

        log("allow", host, port)
        self.connection.sendall(b"HTTP/1.1 200 Connection Established\r\nProxy-Agent: poc-allowlist\r\n\r\n")
        try:
            sockets = (self.connection, upstream)
            while True:
                readable, _, exceptional = select.select(sockets, (), sockets, 20)
                if exceptional or not readable:
                    break
                for source in readable:
                    data = source.recv(65536)
                    if not data:
                        return
                    target = upstream if source is self.connection else self.connection
                    target.sendall(data)
        except OSError:
            pass
        finally:
            upstream.close()

    def _deny_non_connect(self):
        log("deny", self.path[:120], 0, "only HTTPS CONNECT is supported")
        self.send_error(403, "only allowlisted HTTPS CONNECT is supported")

    do_GET = _deny_non_connect
    do_POST = _deny_non_connect
    do_PUT = _deny_non_connect
    do_DELETE = _deny_non_connect
    do_HEAD = _deny_non_connect


if __name__ == "__main__":
    print(json.dumps({"event": "listening", "address": LISTEN, "allowed_hosts": sorted(ALLOWLIST), "allowed_port": 443}), flush=True)
    ThreadingHTTPServer(LISTEN, ProxyHandler).serve_forever()

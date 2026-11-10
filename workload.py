#!/usr/bin/env python3
"""Small dependency-free workloads for paired runc/runsc smoke measurements."""

import hashlib
import http.client
import json
import mmap
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def cpu_work():
    value = b"gvisor-poc"
    start = time.perf_counter()
    for _ in range(300_000):
        value = hashlib.sha256(value).digest()
    return {"work": "cpu", "iterations": 300_000, "digest": value.hex(), "seconds": time.perf_counter() - start}


def io_work():
    chunk = bytes(range(256)) * 4096
    digest = hashlib.sha256()
    start = time.perf_counter()
    with tempfile.NamedTemporaryFile(dir="/tmp") as f:
        for _ in range(8):
            f.write(chunk)
        f.flush()
        os.fsync(f.fileno())
        f.seek(0)
        for data in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(data)
    return {"work": "io", "bytes": len(chunk) * 8, "digest": digest.hexdigest(), "seconds": time.perf_counter() - start}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"poc-ok"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


def http_work():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    start = time.perf_counter()
    count = 200
    try:
        for _ in range(count):
            conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
            conn.request("GET", "/")
            response = conn.getresponse()
            body = response.read()
            conn.close()
            if response.status != 200 or body != b"poc-ok":
                raise RuntimeError("loopback HTTP response mismatch")
    finally:
        server.shutdown()
        server.server_close()
    return {"work": "http", "requests": count, "seconds": time.perf_counter() - start}


def probe_work():
    checks = {}
    observations = {"uid": os.getuid(), "pid": os.getpid()}
    checks["non_root_uid"] = os.getuid() != 0
    checks["process_namespace_pid1"] = os.getpid() == 1
    try:
        with open("/proc/1/status", encoding="utf-8") as f:
            status = f.read()
        checks["proc_pid1_readable"] = "Pid:\t1" in status or "Pid: 1" in status
        observations["visible_proc_pids"] = sorted(int(name) for name in os.listdir("/proc") if name.isdigit())
    except OSError as exc:
        checks["proc_pid1_readable"] = False
        observations["proc_error"] = str(exc)

    try:
        fields = dict(line.split(":", 1) for line in status.splitlines() if ":" in line)
        observations["cap_eff"] = fields.get("CapEff", "").strip()
        observations["no_new_privs"] = fields.get("NoNewPrivs", "").strip()
        checks["effective_capabilities_dropped"] = int(fields.get("CapEff", "0"), 16) == 0
        checks["no_new_privileges_set"] = fields.get("NoNewPrivs", "").strip() == "1"
    except (NameError, ValueError):
        checks["effective_capabilities_dropped"] = False
        checks["no_new_privileges_set"] = False

    sentinel = os.environ.get("POC_SENTINEL_PATH", "/home/chaitanya.guest/.gvisor-poc-host-sentinel")
    checks["guest_sentinel_not_visible"] = not os.path.exists(sentinel)
    checks["docker_socket_not_visible"] = not any(os.path.exists(p) for p in ("/var/run/docker.sock", "/run/docker.sock"))

    try:
        with open("/opt/poc/.readonly-probe", "wb") as f:
            f.write(b"unexpected writable root")
        checks["rootfs_write_blocked"] = False
    except OSError as exc:
        checks["rootfs_write_blocked"] = exc.errno == 30  # EROFS
        observations["rootfs_write_errno"] = exc.errno

    try:
        with tempfile.NamedTemporaryFile(dir="/tmp") as f:
            f.write(b"tmp-write-ok")
            f.flush()
        checks["tmp_write_allowed"] = True
    except OSError as exc:
        checks["tmp_write_allowed"] = False
        observations["tmp_error"] = str(exc)

    try:
        checks["getrandom_available"] = len(os.urandom(16)) == 16
        with mmap.mmap(-1, 4096) as region:
            region[:4] = b"poc!"
            checks["anonymous_mmap_available"] = region[:4] == b"poc!"
        event = threading.Event()
        thread = threading.Thread(target=event.set)
        thread.start()
        thread.join(timeout=2)
        checks["thread_create_join"] = event.is_set()
    except OSError as exc:
        observations["syscall_error"] = str(exc)
        checks.setdefault("getrandom_available", False)
        checks.setdefault("anonymous_mmap_available", False)
        checks.setdefault("thread_create_join", False)

    try:
        result = subprocess.run(
            [sys.executable, "-c", "import os; os.setuid(0)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=2,
            check=False,
        )
        checks["setuid_root_denied"] = result.returncode != 0
    except (OSError, subprocess.TimeoutExpired):
        checks["setuid_root_denied"] = True
    sudo = shutil.which("sudo")
    if sudo:
        try:
            result = subprocess.run([sudo, "-n", "true"], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=2, check=False)
            checks["sudo_cannot_escalate"] = result.returncode != 0
        except (OSError, subprocess.TimeoutExpired):
            checks["sudo_cannot_escalate"] = True
    else:
        checks["sudo_cannot_escalate"] = True
        observations["sudo"] = "not installed"

    try:
        with socket.socket() as server:
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            server.settimeout(2)
            with socket.create_connection(server.getsockname(), timeout=2) as client:
                conn, _ = server.accept()
                with conn:
                    conn.sendall(b"loopback-ok")
                    checks["loopback_socket"] = client.recv(32) == b"loopback-ok"
    except OSError as exc:
        observations["loopback_error"] = str(exc)
        checks["loopback_socket"] = False

    try:
        with socket.create_connection(("192.0.2.1", 80), timeout=0.5):
            checks["external_network_blocked"] = False
    except OSError:
        checks["external_network_blocked"] = True

    result = {"work": "isolation-probes", "checks": checks, "observations": observations}
    result["passed"] = all(checks.values())
    result["python"] = os.sys.version.split()[0]
    print(json.dumps(result, sort_keys=True))
    if not result["passed"]:
        raise SystemExit(1)


def blocked_by_proxy(opener, url):
    try:
        with opener.open(url, timeout=8) as response:
            response.read(64)
        return False, "request unexpectedly succeeded"
    except urllib.error.URLError as exc:
        reason = str(exc)
        return "403" in reason, reason
    except OSError as exc:
        reason = str(exc)
        return "403" in reason, reason


def network_probe_work():
    proxy = os.environ.get("POC_HTTPS_PROXY", "http://egress-proxy:3128")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({"https": proxy}))
    checks = {}
    observations = {"proxy": proxy, "allowlisted_host": "example.com", "denied_host": "example.org"}

    try:
        with opener.open("https://example.com/", timeout=12) as response:
            body = response.read(256)
            checks["allowlisted_https_succeeds"] = 200 <= response.status < 400 and len(body) > 0
            observations["allowlisted_http_status"] = response.status
    except Exception as exc:
        checks["allowlisted_https_succeeds"] = False
        observations["allowlisted_error"] = str(exc)

    checks["non_allowlisted_domain_denied"], observations["non_allowlisted_error"] = blocked_by_proxy(
        opener, "https://example.org/"
    )
    checks["ip_literal_denied"], observations["ip_literal_error"] = blocked_by_proxy(
        opener, "https://1.1.1.1/"
    )
    checks["non_allowlisted_port_denied"], observations["non_allowlisted_port_error"] = blocked_by_proxy(
        opener, "https://example.com:8443/"
    )

    try:
        with socket.create_connection(("1.1.1.1", 443), timeout=1):
            checks["direct_egress_blocked"] = False
            observations["direct_egress_error"] = "direct connection unexpectedly succeeded"
    except OSError as exc:
        checks["direct_egress_blocked"] = True
        observations["direct_egress_error"] = str(exc)

    result = {"work": "network-allowlist-probes", "checks": checks, "observations": observations}
    result["passed"] = all(checks.values())
    result["python"] = sys.version.split()[0]
    print(json.dumps(result, sort_keys=True))
    if not result["passed"]:
        raise SystemExit(1)


def main():
    import sys

    modes = {"cpu": cpu_work, "io": io_work, "http": http_work, "probe": probe_work, "network-probe": network_probe_work}
    if len(sys.argv) != 2 or sys.argv[1] not in modes:
        raise SystemExit("usage: workload.py {cpu|io|http|probe|network-probe}")
    result = modes[sys.argv[1]]()
    if sys.argv[1] not in {"probe", "network-probe"}:
        result["python"] = os.sys.version.split()[0]
        print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Small dependency-free workloads for paired runc/runsc smoke measurements."""

import hashlib
import http.client
import json
import mmap
import os
import socket
import tempfile
import threading
import time
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

    sentinel = os.environ.get("POC_SENTINEL_PATH", "/home/chaitanya.guest/.gvisor-poc-host-sentinel")
    checks["guest_sentinel_not_visible"] = not os.path.exists(sentinel)

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


def main():
    import sys

    modes = {"cpu": cpu_work, "io": io_work, "http": http_work, "probe": probe_work}
    if len(sys.argv) != 2 or sys.argv[1] not in modes:
        raise SystemExit("usage: workload.py {cpu|io|http|probe}")
    result = modes[sys.argv[1]]()
    if sys.argv[1] != "probe":
        result["python"] = os.sys.version.split()[0]
        print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Small dependency-free workloads for paired runc/runsc smoke measurements."""

import hashlib
import errno
import http.client
import json
import mmap
import os
import platform
import ctypes
import select
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
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
    protocol_version = "HTTP/1.1"
    tcp_nodelay = False

    def setup(self):
        super().setup()
        if self.tcp_nodelay:
            self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

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
            conn.request("GET", "/", headers={"Connection": "close"})
            response = conn.getresponse()
            body = response.read()
            conn.close()
            if response.status != 200 or body != b"poc-ok":
                raise RuntimeError("loopback HTTP response mismatch")
    finally:
        server.shutdown()
        server.server_close()
    return {"work": "http", "requests": count, "seconds": time.perf_counter() - start}


def http_keepalive_work():
    """Measure serial loopback HTTP requests over one persistent connection."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    start = time.perf_counter()
    count = 200
    conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    try:
        for _ in range(count):
            conn.request("GET", "/")
            response = conn.getresponse()
            body = response.read()
            if response.status != 200 or body != b"poc-ok":
                raise RuntimeError("loopback HTTP response mismatch")
    finally:
        conn.close()
        server.shutdown()
        server.server_close()
    return {
        "work": "http-keepalive",
        "requests": count,
        "connections": 1,
        "connection_policy": "keep-alive",
        "seconds": time.perf_counter() - start,
    }


class NoDelayHandler(Handler):
    tcp_nodelay = True


def http_keepalive_nodelay_work():
    """Measure one persistent connection with TCP_NODELAY on client and server."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), NoDelayHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    count = 200
    conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    start = time.perf_counter()
    try:
        conn.connect()
        conn.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        for _ in range(count):
            conn.request("GET", "/")
            response = conn.getresponse()
            body = response.read()
            if response.status != 200 or body != b"poc-ok":
                raise RuntimeError("loopback HTTP response mismatch")
    finally:
        conn.close()
        server.shutdown()
        server.server_close()
    return {
        "work": "http-keepalive-nodelay",
        "requests": count,
        "connections": 1,
        "connection_policy": "keep-alive",
        "tcp_nodelay_client": True,
        "tcp_nodelay_server": True,
        "seconds": time.perf_counter() - start,
    }


def http_concurrent_keepalive_work(tcp_nodelay=False):
    """Measure 200 requests on eight concurrent persistent loopback connections."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), NoDelayHandler if tcp_nodelay else Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    clients = 8
    requests_per_client = 25
    start = time.perf_counter()

    def client_work(_client_id):
        conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
        try:
            if tcp_nodelay:
                conn.connect()
                conn.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            for _ in range(requests_per_client):
                conn.request("GET", "/")
                response = conn.getresponse()
                body = response.read()
                if response.status != 200 or body != b"poc-ok":
                    raise RuntimeError("loopback HTTP response mismatch")
        finally:
            conn.close()

    try:
        with ThreadPoolExecutor(max_workers=clients) as pool:
            list(pool.map(client_work, range(clients)))
    finally:
        server.shutdown()
        server.server_close()
    return {
        "work": "http-concurrent-keepalive-nodelay" if tcp_nodelay else "http-concurrent-keepalive",
        "requests": clients * requests_per_client,
        "connections": clients,
        "requests_per_connection": requests_per_client,
        "connection_policy": "keep-alive",
        "concurrent_clients": clients,
        "tcp_nodelay_client": tcp_nodelay,
        "tcp_nodelay_server": tcp_nodelay,
        "seconds": time.perf_counter() - start,
    }


def http_concurrent_keepalive_nodelay_work():
    return http_concurrent_keepalive_work(tcp_nodelay=True)


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
        checks["private_process_view"] = observations["visible_proc_pids"] == [1]
    except OSError as exc:
        checks["proc_pid1_readable"] = False
        checks["private_process_view"] = False
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

    outside_write_results = {}
    for path in (f"/etc/.poc-write-probe-{os.getpid()}", f"/var/tmp/.poc-write-probe-{os.getpid()}"):
        try:
            with open(path, "xb") as f:
                f.write(b"synthetic")
            os.unlink(path)
            outside_write_results[path] = False
        except OSError:
            outside_write_results[path] = True
    checks["writes_outside_tmp_blocked"] = all(outside_write_results.values())
    observations["outside_write_denials"] = outside_write_results

    try:
        with tempfile.TemporaryDirectory(dir="/tmp") as temp_dir:
            link = os.path.join(temp_dir, "etc-link")
            os.symlink("/etc", link)
            try:
                symlink_target = os.path.join(link, f".poc-symlink-write-probe-{os.getpid()}")
                with open(symlink_target, "xb") as f:
                    f.write(b"synthetic")
                os.unlink(symlink_target)
                checks["symlink_traversal_write_blocked"] = False
            except OSError:
                checks["symlink_traversal_write_blocked"] = True
    except OSError as exc:
        checks["symlink_traversal_write_blocked"] = False
        observations["symlink_probe_error"] = str(exc)

    try:
        checks["sysfs_read_only"] = bool(os.statvfs("/sys").f_flag & getattr(os, "ST_RDONLY", 1))
    except OSError as exc:
        checks["sysfs_read_only"] = False
        observations["sysfs_error"] = str(exc)

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


def syscall_matrix_work():
    """Record harmless kernel-interface probe outcomes; do not treat this as an escape test."""
    if not sys.platform.startswith("linux"):
        raise SystemExit("syscall matrix must run inside the Linux guest")
    machine = platform.machine().lower()
    numbers = {
        "aarch64": {"bpf": 280, "keyctl": 219, "ptrace": 117, "perf_event_open": 241, "userfaultfd": 282},
        "x86_64": {"bpf": 321, "keyctl": 250, "ptrace": 101, "perf_event_open": 298, "userfaultfd": 323},
    }.get(machine)
    if numbers is None:
        raise SystemExit(f"syscall matrix has no syscall numbers for {machine}")

    child_program = r'''import ctypes, errno, json, os, sys
name, number = sys.argv[1], int(sys.argv[2])
libc = ctypes.CDLL(None, use_errno=True)
if name == "mount-invalid-fstype":
    libc.mount.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_void_p]
    libc.mount.restype = ctypes.c_int
    ctypes.set_errno(0)
    result = libc.mount(b"none", b"/tmp", b"poc-no-such-filesystem", 0, None)
elif name == "unshare-mount-namespace":
    libc.unshare.argtypes = [ctypes.c_int]
    libc.unshare.restype = ctypes.c_int
    ctypes.set_errno(0)
    result = libc.unshare(0x00020000)  # CLONE_NEWNS; the child exits immediately if permitted.
else:
    number = int(number)
    libc.syscall.restype = ctypes.c_long
    ctypes.set_errno(0)
    if name == "bpf-invalid-command":
        result = libc.syscall(number, 0xffffffff, 0, 0)
    elif name == "keyctl-invalid-operation":
        result = libc.syscall(number, -1, 0, 0, 0, 0)
    elif name == "ptrace-invalid-request":
        result = libc.syscall(number, 0x7fffffff, 0, 0, 0)
    elif name == "perf-event-open-null-attr":
        result = libc.syscall(number, 0, -1, 0, -1, 0)
    elif name == "userfaultfd-create-close":
        result = libc.syscall(number, 0x80000 | 0x800)  # O_CLOEXEC | O_NONBLOCK
        if result >= 0:
            os.close(result)
    else:
        raise SystemExit("unknown syscall probe")
error = ctypes.get_errno() if result < 0 else 0
print(json.dumps({"return": int(result), "errno": error, "errno_name": errno.errorcode.get(error, "")}, sort_keys=True))
'''

    probes = [
        ("mount-invalid-fstype", 0),
        ("unshare-mount-namespace", 0),
        ("bpf-invalid-command", numbers["bpf"]),
        ("keyctl-invalid-operation", numbers["keyctl"]),
        ("ptrace-invalid-request", numbers["ptrace"]),
        ("perf-event-open-null-attr", numbers["perf_event_open"]),
        ("userfaultfd-create-close", numbers["userfaultfd"]),
    ]
    outcomes = {}
    for name, number in probes:
        try:
            child = subprocess.run(
                [sys.executable, "-c", child_program, name, str(number)],
                capture_output=True, text=True, timeout=3, check=False,
            )
            try:
                detail = json.loads(child.stdout.strip().splitlines()[-1])
                code = detail["errno"]
                classification = "permitted" if detail["return"] >= 0 else (
                    "blocked" if code in (errno.EPERM, errno.EACCES) else
                    "unsupported" if code == errno.ENOSYS else "rejected-invalid-probe"
                )
                outcomes[name] = {"classification": classification, **detail, "child_exit": child.returncode}
            except (IndexError, KeyError, json.JSONDecodeError):
                outcomes[name] = {
                    "classification": "terminated-or-no-result",
                    "child_exit": child.returncode,
                    "stderr": child.stderr[-300:],
                }
        except subprocess.TimeoutExpired:
            outcomes[name] = {"classification": "timed-out"}

    status = {}
    try:
        with open("/proc/self/status", encoding="utf-8") as stream:
            fields = dict(line.split(":", 1) for line in stream if ":" in line)
        status = {"cap_eff": fields.get("CapEff", "").strip(), "no_new_privs": fields.get("NoNewPrivs", "").strip()}
    except OSError as exc:
        status = {"status_error": str(exc)}

    sentinel = os.environ.get("POC_SYSCALL_SENTINEL_PATH", "/home/chaitanya.guest/.gvisor-poc-syscall-sentinel")
    checks = {
        "non_root_uid": os.getuid() != 0,
        "effective_capabilities_dropped": status.get("cap_eff") == "0000000000000000",
        "no_new_privileges_set": status.get("no_new_privs") == "1",
        "guest_sentinel_not_visible": not os.path.exists(sentinel),
        "all_syscalls_recorded": len(outcomes) == len(probes),
    }
    observations = {
        "uid": os.getuid(),
        "pid": os.getpid(),
        "architecture": machine,
        "kernel_release": platform.release(),
        "seccomp_mode": os.environ.get("POC_SYSCALL_SECCOMP_MODE", "unspecified"),
        "seccomp_profile_sha256": os.environ.get("POC_SYSCALL_PROFILE_SHA256") or None,
        "cap_eff": status.get("cap_eff"),
        "no_new_privs": status.get("no_new_privs"),
        "sentinel_path_visible": os.path.exists(sentinel),
        "syscall_matrix": outcomes,
        "interpretation": "Observed syscall outcomes only; permitted, rejected, or unsupported does not prove runtime security.",
    }
    result = {"work": "kernel-interface-syscall-matrix", "checks": checks, "observations": observations}
    result["passed"] = all(checks.values())
    result["python"] = sys.version.split()[0]
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
    from urllib.parse import urlsplit

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

    proxy_parts = urlsplit(proxy)

    def raw_proxy_status(request_line, host_header):
        with socket.create_connection((proxy_parts.hostname, proxy_parts.port or 3128), timeout=3) as client:
            client.settimeout(5)
            request = f"{request_line}\r\nHost: {host_header}\r\nConnection: close\r\n\r\n"
            client.sendall(request.encode("ascii"))
            first_line = client.recv(4096).split(b"\r\n", 1)[0].decode("ascii", "replace")
            return int(first_line.split()[1]), first_line

    raw_cases = {
        "proxy_rejects_plain_http_method": ("GET http://example.com/ HTTP/1.1", "example.com"),
        "proxy_rejects_unlisted_connect_with_allowed_host_header": ("CONNECT example.org:443 HTTP/1.1", "example.com:443"),
        "proxy_rejects_alternate_port_connect": ("CONNECT example.com:8443 HTTP/1.1", "example.com:443"),
        "proxy_rejects_lookalike_subdomain": ("CONNECT example.com.attacker.invalid:443 HTTP/1.1", "example.com:443"),
        "proxy_rejects_ip_connect_with_allowed_host_header": ("CONNECT 1.1.1.1:443 HTTP/1.1", "example.com:443"),
        "proxy_rejects_userinfo_authority": ("CONNECT example.com:443@attacker.invalid HTTP/1.1", "example.com:443"),
        "proxy_rejects_bracketed_ipv6_connect": ("CONNECT [2606:4700:4700::1111]:443 HTTP/1.1", "example.com:443"),
    }
    raw_statuses = {}
    for name, (request_line, host_header) in raw_cases.items():
        try:
            status, response = raw_proxy_status(request_line, host_header)
            checks[name] = status == 403
            raw_statuses[name] = response
        except (OSError, ValueError, IndexError) as exc:
            checks[name] = False
            raw_statuses[name] = str(exc)
    observations["raw_proxy_responses"] = raw_statuses

    # Exercise additional HTTP method/parser paths and authority canonicalization.
    protocol_cases = {
        "proxy_rejects_trace_method": ("TRACE * HTTP/1.1", "example.com"),
        "proxy_rejects_options_absolute_form": ("OPTIONS http://example.com/ HTTP/1.1", "example.com"),
        "proxy_rejects_https_absolute_form_without_connect": ("GET https://example.com/ HTTP/1.1", "example.com"),
        "proxy_rejects_encoded_lookalike_host": ("CONNECT example.com%2eattacker.invalid:443 HTTP/1.1", "example.com:443"),
        "proxy_rejects_multiple_authorities": ("CONNECT example.com:443,example.org:443 HTTP/1.1", "example.com:443"),
    }
    for name, (request_line, host_header) in protocol_cases.items():
        try:
            status, response = raw_proxy_status(request_line, host_header)
            checks[name] = status >= 400
            raw_statuses[name] = response
        except (OSError, ValueError, IndexError) as exc:
            checks[name] = False
            raw_statuses[name] = str(exc)

    authority_controls = {
        "proxy_accepts_case_normalized_allowlisted_target": ("CONNECT EXAMPLE.COM:443 HTTP/1.1", "example.com:443"),
        "proxy_accepts_trailing_dot_allowlisted_target": ("CONNECT example.com.:443 HTTP/1.1", "example.com.:443"),
        "allowlist_uses_connect_authority_not_host_header": ("CONNECT example.com:443 HTTP/1.1", "example.org:443"),
    }
    for name, (request_line, host_header) in authority_controls.items():
        try:
            status, response = raw_proxy_status(request_line, host_header)
            checks[name] = status == 200
            raw_statuses[name] = response
        except (OSError, ValueError, IndexError) as exc:
            checks[name] = False
            raw_statuses[name] = str(exc)

    # CONNECT is an opaque TCP tunnel: observe whether an unlisted TLS SNI name
    # can be sent through a tunnel authorized for the allowlisted CONNECT host.
    # This is informative about policy limits and is not counted as a test pass.
    sni_observation = {"connect_authority": "example.com:443", "tls_server_name": "example.org"}
    try:
        client = socket.create_connection((proxy_parts.hostname, proxy_parts.port or 3128), timeout=5)
        client.settimeout(5)
        client.sendall(b"CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\nConnection: keep-alive\r\n\r\n")
        connect_response = client.recv(4096).split(b"\r\n", 1)[0].decode("ascii", "replace")
        sni_observation["connect_response"] = connect_response
        if connect_response.split()[1] == "200":
            context = ssl._create_unverified_context()
            with context.wrap_socket(client, server_hostname="example.org") as tunnel:
                tunnel.sendall(b"GET / HTTP/1.1\r\nHost: example.org\r\nConnection: close\r\n\r\n")
                response = tunnel.recv(4096).split(b"\r\n", 1)[0].decode("ascii", "replace")
            sni_observation["tls_handshake_succeeded"] = True
            sni_observation["http_response"] = response
            sni_observation["strict_domain_allowlist_enforced"] = False
        else:
            client.close()
            sni_observation["tls_handshake_succeeded"] = False
            sni_observation["strict_domain_allowlist_enforced"] = True
    except Exception as exc:
        sni_observation["tls_handshake_succeeded"] = False
        sni_observation["strict_domain_allowlist_enforced"] = None
        sni_observation["error"] = str(exc)
    observations["unlisted_tls_sni_over_allowlisted_connect"] = sni_observation

    redirect_url = os.environ.get("POC_REDIRECT_TEST_URL")
    if redirect_url:
        checks["redirect_to_denied_domain_blocked"], observations["redirect_probe_error"] = blocked_by_proxy(
            opener, redirect_url
        )
    checks["ipv6_literal_denied"], observations["ipv6_literal_error"] = blocked_by_proxy(
        opener, "https://[2606:4700:4700::1111]/"
    )

    # Unit-probe the proxy's resolve/validate/connect sequence with synthetic DNS answers.
    # A private answer is rejected, and only the validated public sockaddr is connected.
    try:
        from unittest.mock import patch
        import allowlist_proxy

        private = (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 443))
        public = (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 443))
        connected = []

        class FakeSocket:
            def settimeout(self, _timeout):
                pass

            def connect(self, sockaddr):
                connected.append(sockaddr)

            def close(self):
                pass

        with patch("allowlist_proxy.socket.getaddrinfo", return_value=[private, public]), patch(
            "allowlist_proxy.socket.socket", side_effect=lambda *_args: FakeSocket()
        ):
            upstream = allowlist_proxy.connect_public("synthetic.example", 443)
            upstream.close()
        checks["proxy_rejects_private_dns_answer"] = connected == [public[4]]
        observations["dns_answer_probe"] = {"private_answer_skipped": True, "connected_sockaddrs": connected}
    except Exception as exc:
        checks["proxy_rejects_private_dns_answer"] = False
        observations["dns_answer_probe_error"] = str(exc)

    try:
        with socket.create_connection(("1.1.1.1", 443), timeout=1):
            checks["direct_egress_blocked"] = False
            observations["direct_egress_error"] = "direct connection unexpectedly succeeded"
    except OSError as exc:
        checks["direct_egress_blocked"] = True
        observations["direct_egress_error"] = str(exc)

    try:
        with socket.create_connection(("2606:4700:4700::1111", 443), timeout=1):
            checks["direct_ipv6_egress_blocked"] = False
            observations["direct_ipv6_egress_error"] = "direct IPv6 connection unexpectedly succeeded"
    except OSError as exc:
        checks["direct_ipv6_egress_blocked"] = True
        observations["direct_ipv6_egress_error"] = str(exc)

    try:
        qname = b"\x07example\x03com\x00"
        query = b"\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00" + qname + b"\x00\x01\x00\x01"
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
            udp.settimeout(1)
            udp.connect(("1.1.1.1", 53))
            udp.sendall(query)
            response = udp.recv(512)
        answers = int.from_bytes(response[6:8], "big") if len(response) >= 8 else 0
        checks["direct_udp_dns_blocked"] = not (response[:2] == b"\x12\x34" and answers > 0)
        observations["direct_udp_dns_response_bytes"] = len(response)
    except OSError as exc:
        checks["direct_udp_dns_blocked"] = True
        observations["direct_udp_dns_error"] = str(exc)

    result = {"work": "network-allowlist-probes", "checks": checks, "observations": observations}
    result["passed"] = all(checks.values())
    result["python"] = sys.version.split()[0]
    print(json.dumps(result, sort_keys=True))
    if not result["passed"]:
        raise SystemExit(1)


def dns_rebind_probe_work():
    from urllib.parse import urlsplit

    proxy = urlsplit(os.environ.get("POC_HTTPS_PROXY", "http://egress-proxy:3128"))
    host = os.environ.get("POC_REBIND_TARGET", "example.com")
    port = proxy.port or 3128

    def connect_status():
        with socket.create_connection((proxy.hostname, port), timeout=5) as sock:
            sock.settimeout(8)
            sock.sendall(f"CONNECT {host}:443 HTTP/1.1\r\nHost: {host}:443\r\n\r\n".encode("ascii"))
            response = sock.recv(4096).split(b"\r\n", 1)[0].decode("ascii", "replace")
            return int(response.split()[1]), response

    first_status, first_response = connect_status()
    second_status, second_response = connect_status()
    checks = {"initial_public_answer_connects": first_status == 200,
              "rebound_loopback_answer_rejected": second_status == 502}
    result = {"work": "dns-rebinding-probe", "checks": checks,
              "observations": {"target": host, "first_proxy_status": first_status,
                               "first_response": first_response, "second_proxy_status": second_status,
                               "second_response": second_response,
                               "interpretation": "Controlled DNS response changed from a public address to loopback; each proxy resolution was validated before connect."}}
    result["passed"] = all(checks.values())
    result["python"] = sys.version.split()[0]
    print(json.dumps(result, sort_keys=True))
    if not result["passed"]:
        raise SystemExit(1)


def syscall_compatibility_work():
    checks = {}
    observations = {"uid": os.getuid(), "kernel": platform.release()}

    try:
        with tempfile.TemporaryDirectory(dir="/tmp") as temp_dir:
            directory_fd = os.open(temp_dir, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                fd = os.open("relative-file", os.O_CREAT | os.O_RDWR, 0o600, dir_fd=directory_fd)
                try:
                    os.write(fd, b"openat-ok")
                    os.lseek(fd, 0, os.SEEK_SET)
                    checks["openat_relative_read_write"] = os.read(fd, 32) == b"openat-ok"
                finally:
                    os.close(fd)
            finally:
                os.close(directory_fd)
    except OSError as exc:
        checks["openat_relative_read_write"] = False
        observations["openat_error"] = str(exc)

    try:
        fd = os.memfd_create("poc-memfd", 0)
        try:
            os.write(fd, b"memfd-ok")
            os.lseek(fd, 0, os.SEEK_SET)
            with mmap.mmap(fd, 8) as view:
                checks["memfd_mmap"] = view[:] == b"memfd-ok"
        finally:
            os.close(fd)
    except (AttributeError, OSError) as exc:
        checks["memfd_mmap"] = False
        observations["memfd_error"] = str(exc)

    try:
        pidfd = os.pidfd_open(os.getpid(), 0)
        try:
            checks["pidfd_open_self"] = os.fstat(pidfd).st_ino > 0
        finally:
            os.close(pidfd)
    except (AttributeError, OSError) as exc:
        checks["pidfd_open_self"] = False
        observations["pidfd_open_error"] = str(exc)

    try:
        payload = b"copy-file-range-safe-probe"
        with tempfile.TemporaryDirectory(dir="/tmp") as temp_dir:
            source_path = os.path.join(temp_dir, "source")
            target_path = os.path.join(temp_dir, "target")
            with open(source_path, "wb") as source:
                source.write(payload)
            with open(source_path, "rb") as source, open(target_path, "wb") as target:
                copied = os.copy_file_range(source.fileno(), target.fileno(), len(payload))
            with open(target_path, "rb") as target:
                checks["copy_file_range_tmp"] = copied == len(payload) and target.read() == payload
    except (AttributeError, OSError) as exc:
        checks["copy_file_range_tmp"] = False
        observations["copy_file_range_error"] = str(exc)

    try:
        fd = os.eventfd(0, 0)
        try:
            os.write(fd, (3).to_bytes(8, "little"))
            checks["eventfd_round_trip"] = os.read(fd, 8) == (3).to_bytes(8, "little")
        finally:
            os.close(fd)
    except (AttributeError, OSError) as exc:
        checks["eventfd_round_trip"] = False
        observations["eventfd_error"] = str(exc)

    try:
        read_fd, write_fd = os.pipe()
        try:
            with select.epoll() as poller:
                poller.register(read_fd, select.EPOLLIN)
                os.write(write_fd, b"e")
                checks["epoll_pipe_readiness"] = any(poller.poll(1)) and os.read(read_fd, 1) == b"e"
        finally:
            os.close(read_fd)
            os.close(write_fd)
    except OSError as exc:
        checks["epoll_pipe_readiness"] = False
        observations["epoll_error"] = str(exc)

    try:
        left, right = socket.socketpair()
        try:
            left.sendall(b"socketpair-ok")
            checks["unix_socketpair"] = right.recv(32) == b"socketpair-ok"
        finally:
            left.close()
            right.close()
    except OSError as exc:
        checks["unix_socketpair"] = False
        observations["socketpair_error"] = str(exc)

    try:
        child = subprocess.run(["/bin/true"], timeout=3, check=False)
        checks["exec_wait_child"] = child.returncode == 0
        observations["child_exit"] = child.returncode
    except (OSError, subprocess.TimeoutExpired) as exc:
        checks["exec_wait_child"] = False
        observations["child_error"] = str(exc)

    try:
        event = threading.Event()
        thread = threading.Thread(target=event.set)
        thread.start()
        thread.join(timeout=2)
        checks["thread_clone_join"] = event.is_set()
    except RuntimeError as exc:
        checks["thread_clone_join"] = False
        observations["thread_error"] = str(exc)

    result = {"work": "syscall-compatibility", "checks": checks, "observations": observations}
    result["passed"] = bool(checks) and all(checks.values())
    result["python"] = sys.version.split()[0]
    print(json.dumps(result, sort_keys=True))
    if not result["passed"]:
        raise SystemExit(1)


def main():
    import sys

    modes = {"cpu": cpu_work, "io": io_work, "http": http_work, "http-keepalive": http_keepalive_work, "http-keepalive-nodelay": http_keepalive_nodelay_work, "http-concurrent-keepalive": http_concurrent_keepalive_work, "http-concurrent-keepalive-nodelay": http_concurrent_keepalive_nodelay_work, "probe": probe_work, "network-probe": network_probe_work, "dns-rebind-probe": dns_rebind_probe_work, "syscall-matrix": syscall_matrix_work, "syscall-compatibility": syscall_compatibility_work}
    if len(sys.argv) != 2 or sys.argv[1] not in modes:
        raise SystemExit("usage: workload.py {cpu|io|http|http-keepalive|http-keepalive-nodelay|http-concurrent-keepalive|http-concurrent-keepalive-nodelay|probe|network-probe|dns-rebind-probe|syscall-matrix|syscall-compatibility}")
    result = modes[sys.argv[1]]()
    if sys.argv[1] not in {"probe", "network-probe", "dns-rebind-probe", "syscall-matrix", "syscall-compatibility"}:
        result["python"] = os.sys.version.split()[0]
        print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()

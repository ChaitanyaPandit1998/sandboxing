"""Bounded owner-only offline export. Caller holds the worker lifecycle lock."""
import base64
import io
import os
from pathlib import PurePosixPath
import selectors
import subprocess
import tarfile
import time
import uuid
from manage_codex_session import AGENT, RUNTIME, WorkerError
from workspace_storage import checked_volume

MAX_ARCHIVE_BYTES = 16 * 1024**2
MAX_ENTRIES = 10000


def capture_archive(command, limit=MAX_ARCHIVE_BYTES, timeout=30):
    """Bound stdout in memory while draining; never capture private tar stderr."""
    data = bytearray()
    deadline = time.monotonic() + timeout
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as process:
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0 or not selector.select(remaining):
                        raise WorkerError('workspace_export_timeout')
                    chunk = os.read(process.stdout.fileno(), 65536)
                    if not chunk:
                        break
                    if len(data) + len(chunk) > limit:
                        raise WorkerError('workspace_export_too_large')
                    data.extend(chunk)
                if process.wait(timeout=max(.001, deadline-time.monotonic())) != 0:
                    raise WorkerError('workspace_export_failed')
        except subprocess.TimeoutExpired:
            raise WorkerError('workspace_export_timeout') from None
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
    return bytes(data)


def validate_archive(data):
    """Inspect only; never extract workspace contents onto the worker or Mac."""
    if not data or len(data) > MAX_ARCHIVE_BYTES:
        raise WorkerError('workspace_export_too_large' if data else 'workspace_export_invalid')
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:') as archive:
            count = 0
            for item in archive:
                count += 1
                path = PurePosixPath(item.name)
                if (count > MAX_ENTRIES or path.is_absolute() or '..' in path.parts
                        or '\\' in item.name or ':' in item.name
                        or any(ord(char) < 32 or ord(char) == 127 for char in item.name)
                        or (item.isfile() and str(path) == '.')
                        or not (item.isfile() or item.isdir()) or item.size < 0
                        or item.offset_data + item.size > len(data)):
                    raise WorkerError('workspace_export_unsafe_or_incomplete')
            if not count:
                raise WorkerError('workspace_export_invalid')
    except (tarfile.TarError, ValueError, EOFError):
        raise WorkerError('workspace_export_invalid') from None


def export_workspace(worker):
    if checked_volume(worker) is None:
        raise WorkerError('workspace_not_found')
    if worker.db.execute("SELECT 1 FROM sessions WHERE owner=? AND state IN ('ready','provisioning','stopping') LIMIT 1", (worker.principal,)).fetchone():
        raise WorkerError('workspace_in_use')
    if worker.docker('ps', '-q', '--filter', 'volume='+worker.volume):
        raise WorkerError('workspace_in_use')
    name = 'poc-workspace-export-' + uuid.uuid4().hex
    try:
        data = capture_archive(['docker', 'run', '--name', name, '--pull=never',
            '--label', worker.label, '--label', 'poc.purpose=workspace-export',
            '--runtime='+RUNTIME, '--network=none', '--read-only', '--user=10001:10001',
            '--cpus=1', '--memory=128m', '--pids-limit=32', '--cap-drop=ALL',
            '--security-opt=no-new-privileges', '--mount',
            'type=volume,source='+worker.volume+',target=/workspace,readonly',
            '--entrypoint=tar', AGENT, '--format=ustar', '--one-file-system', '-cf', '-', '-C', '/workspace', '.'])
        validate_archive(data)
        return {'archive_base64': base64.b64encode(data).decode('ascii')}
    finally:
        try:
            worker.docker('rm', '-f', name)
        except WorkerError:
            if worker.exists('container', name) is not None:
                raise WorkerError('workspace_probe_cleanup_failed') from None

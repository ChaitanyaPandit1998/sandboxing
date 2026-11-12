#!/usr/bin/env python3
"""Resident worker reconciliation loop; no listener, credentials, or model calls."""
import argparse
import json
import os
import pathlib
import signal
import tempfile
import threading
import time
from manage_codex_session import Worker


def save_health(root, value):
    fd, name = tempfile.mkstemp(prefix='.reconciler-', dir=root)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream)
            stream.write('\n')
        os.replace(name, root / 'reconciler-health.json')
    finally:
        if os.path.exists(name):
            os.unlink(name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', default='~/.local/state/gvisor-poc-worker')
    parser.add_argument('--interval', type=float, default=30)
    args = parser.parse_args()
    if not .1 <= args.interval <= 300:
        parser.error('interval must be 0.1–300 seconds')
    root = pathlib.Path(args.state_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    health = {'service': 'gvisor-poc-reconciler', 'interval_seconds': args.interval,
              'last_attempt': None, 'last_success': None, 'error': None}
    while not stop.is_set():
        health['last_attempt'] = time.time()
        save_health(root, health)
        worker = None
        try:
            worker = Worker(root)
            worker.docker('info', '--format', '{{.ServerVersion}}')
            with worker.locked():
                worker.reconcile()
            health.update(last_success=time.time(), error=None)
        except Exception:
            health['error'] = 'worker_unavailable_or_cleanup_failed'
        finally:
            if worker:
                worker.db.close()
        save_health(root, health)
        stop.wait(args.interval)


if __name__ == '__main__':
    main()

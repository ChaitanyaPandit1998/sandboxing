"""Explicit, owner-only deletion of one idle managed volume; no forced removals."""
import hashlib
import json
import re
import secrets
import sqlite3
import time
from manage_codex_session import WorkerError
from workspace_storage import checked_volume

CONFIRMATION = 'DELETE WORKSPACE'
CONFIRMATION_SECONDS = 60


def initialize(worker):
    worker.db.execute('''CREATE TABLE IF NOT EXISTS workspace_deletions
        (token_hash TEXT PRIMARY KEY, owner TEXT NOT NULL, fingerprint TEXT NOT NULL,
         expires REAL NOT NULL, used REAL)''')
    worker.db.commit()


def fingerprint(volume):
    if not volume.get('CreatedAt'):
        raise WorkerError('workspace_identity_unavailable')
    return hashlib.sha256(json.dumps({key: volume.get(key) for key in
        ('Name', 'CreatedAt', 'Labels', 'Driver', 'Options')}, sort_keys=True).encode()).hexdigest()


def require_idle(worker):
    if worker.db.execute("SELECT 1 FROM sessions WHERE owner=? AND state IN ('ready','provisioning','stopping') LIMIT 1", (worker.principal,)).fetchone():
        raise WorkerError('workspace_in_use')
    # Include stopped containers: Docker still retains their volume references.
    if worker.docker('ps', '-aq', '--filter', 'volume='+worker.volume):
        raise WorkerError('workspace_in_use')


def prepare_deletion(worker):
    """Caller holds worker.locked(); this creates consent state, never deletes data."""
    from workspace_migration import block_deletion
    block_deletion(worker)
    initialize(worker)
    volume = checked_volume(worker)
    if volume is None:
        raise WorkerError('workspace_not_found')
    identity = fingerprint(volume)
    require_idle(worker)
    token = secrets.token_hex(32)
    expires = time.time() + CONFIRMATION_SECONDS
    worker.db.execute('DELETE FROM workspace_deletions WHERE owner=? OR expires<?', (worker.principal, time.time()))
    worker.db.execute('INSERT INTO workspace_deletions VALUES(?,?,?,?,NULL)',
        (hashlib.sha256(token.encode()).hexdigest(), worker.principal, identity, expires))
    worker.db.commit()
    return {'token': token, 'owner': worker.principal, 'expires': expires,
            'confirmation': CONFIRMATION, 'irreversible': True}


def delete_workspace(worker, token, confirmation):
    """One-use consent is committed with requested audit before Docker removal."""
    from workspace_migration import block_deletion
    block_deletion(worker)
    initialize(worker)
    if confirmation != CONFIRMATION or not isinstance(token, str) or not re.fullmatch('[a-f0-9]{64}', token):
        raise WorkerError('workspace_confirmation_invalid')
    digest = hashlib.sha256(token.encode()).hexdigest()
    ticket = worker.db.execute('SELECT * FROM workspace_deletions WHERE token_hash=? AND owner=? AND used IS NULL AND expires>?',
        (digest, worker.principal, time.time())).fetchone()
    if ticket is None:
        raise WorkerError('workspace_confirmation_invalid')
    volume = checked_volume(worker)
    if volume is None or fingerprint(volume) != ticket['fingerprint']:
        raise WorkerError('workspace_changed')
    require_idle(worker)
    # The Docker checks may consume the remaining confirmation lifetime.
    if time.time() >= ticket['expires']:
        raise WorkerError('workspace_confirmation_invalid')
    try:
        worker.db.execute('UPDATE workspace_deletions SET used=? WHERE token_hash=?', (time.time(), digest))
        cursor = worker.db.execute('INSERT INTO authorization_audit(actor,action,target,outcome,at) VALUES(?,?,?,?,?)',
            (worker.principal, 'delete_workspace', worker.volume, 'requested', time.time()))
        audit_id = cursor.lastrowid
        worker.db.commit()
    except sqlite3.Error:
        worker.db.rollback()
        raise WorkerError('workspace_audit_unavailable') from None
    try:
        if volume.get('_quota'):
            from workspace_quota import remove
            remove(worker, volume['_quota']['identity'])
            outcome = 'deleted'
        else:
            try:
                worker.docker('volume', 'rm', worker.volume)
            except WorkerError:
                pass  # Resolve uncertain CLI outcomes by inspecting exact volume names.
            remaining = worker.docker('volume', 'ls', '--format', '{{.Name}}', '--filter', 'name='+worker.volume).splitlines()
            outcome = 'failed' if worker.volume in remaining else 'deleted'
    except Exception:
        outcome = 'unknown'
    try:
        worker.db.execute('UPDATE authorization_audit SET outcome=? WHERE id=?', (outcome, audit_id))
        worker.db.commit()
    except sqlite3.Error:
        raise WorkerError('workspace_delete_audit_incomplete') from None
    if outcome != 'deleted':
        raise WorkerError('workspace_delete_failed' if outcome == 'failed' else 'workspace_delete_unknown')
    return {'deleted': True, 'owner': worker.principal, 'audit_id': audit_id}

"""Sanitized local security journal and alert state; uses the worker's private SQLite DB."""
import hashlib
import json
import re
import time
import uuid

KINDS = {'lifecycle', 'lifecycle_failure', 'egress_denied', 'policy_drift', 'egress_burst', 'resource_pressure', 'sample_unavailable', 'collector_gap'}
ACTIONS = {'state_change', 'create', 'cleanup_incomplete', 'expiry_reached', 'login_requested', 'attach_requested'}
STATES = {'ready', 'provisioning', 'stopping', 'stopped', 'failed'}
DETAILS = {'egress_denied': 'Gateway denied traffic. Validation probes may also cause this signal.',
           'policy_drift': 'Selected configuration differs from the approved pilot policy.',
           'lifecycle_failure': 'Worker recorded a failure or incomplete cleanup.'}
DETAILS.update({'egress_burst':'Repeated denied-flow observations reached the review threshold.',
                'resource_pressure':'Resource measurements stayed above a pilot review threshold.',
                'sample_unavailable':'Repeated incomplete monitoring samples reached the review threshold.',
                'collector_gap':'Collection resumed after a gap or a backwards clock change; observations may be missing.'})
MAX_EVENTS = 10000
RETENTION_SECONDS = 30 * 86400


def initialize(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS security_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT, fingerprint TEXT UNIQUE NOT NULL,
      observed_at REAL NOT NULL, session_id TEXT NOT NULL, kind TEXT NOT NULL, detail TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS security_alerts (
      id TEXT PRIMARY KEY, session_id TEXT NOT NULL, kind TEXT NOT NULL, severity TEXT NOT NULL,
      status TEXT NOT NULL, first_seen REAL NOT NULL, last_seen REAL NOT NULL, event_count INTEGER NOT NULL,
      UNIQUE(session_id,kind));
    CREATE TABLE IF NOT EXISTS alert_audit (
      id INTEGER PRIMARY KEY AUTOINCREMENT, alert_id TEXT NOT NULL, action TEXT NOT NULL,
      actor TEXT NOT NULL, at REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS security_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS security_conditions (key TEXT PRIMARY KEY, active INTEGER NOT NULL, generation INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS rule_samples (key TEXT PRIMARY KEY, first_at REAL NOT NULL, last_at REAL NOT NULL, count INTEGER NOT NULL);
    CREATE INDEX IF NOT EXISTS security_events_time ON security_events(observed_at);
    ''')
    columns = {r[1] for r in db.execute('PRAGMA table_info(security_alerts)')}
    if 'resolved_at' not in columns:
        db.execute('ALTER TABLE security_alerts ADD COLUMN resolved_at REAL')
    for table in ('security_events','security_alerts'):
        cols = {r[1] for r in db.execute('PRAGMA table_info(' + table + ')')}
        if 'rules_version' not in cols:
            db.execute("ALTER TABLE " + table + " ADD COLUMN rules_version TEXT NOT NULL DEFAULT 'legacy-observation-v0'")
    db.execute("UPDATE security_alerts SET resolved_at=COALESCE((SELECT MAX(at) FROM alert_audit WHERE alert_id=security_alerts.id AND action='resolve'),last_seen) WHERE status='resolved' AND resolved_at IS NULL")
    db.commit()


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def record(db, fingerprint, sid, kind, detail, at):
    if kind not in KINDS or not re.fullmatch('[a-f0-9]{32}', sid):
        return
    from alert_rules import VERSION
    inserted = db.execute('INSERT OR IGNORE INTO security_events(fingerprint,observed_at,session_id,kind,detail,rules_version) VALUES(?,?,?,?,?,?)',
                          (fingerprint, at, sid, kind, detail, VERSION)).rowcount
    if not inserted or kind == 'lifecycle':
        return
    old = db.execute('SELECT * FROM security_alerts WHERE session_id=? AND kind=?', (sid, kind)).fetchone()
    if old:
        status = 'open' if old['status'] == 'resolved' else old['status']
        db.execute('UPDATE security_alerts SET last_seen=?,event_count=event_count+1,status=?,resolved_at=NULL,rules_version=? WHERE id=?', (at, status, VERSION, old['id']))
        if old['status'] == 'resolved':
            db.execute('INSERT INTO alert_audit(alert_id,action,actor,at) VALUES(?,?,?,?)', (old['id'], 'reopened', 'collector', at))
    else:
        aid = uuid.uuid4().hex
        db.execute('INSERT INTO security_alerts(id,session_id,kind,severity,status,first_seen,last_seen,event_count,rules_version) VALUES(?,?,?,?,?,?,?,?,?)',
                   (aid, sid, kind, 'high' if kind in ('policy_drift','egress_burst') else 'review', 'open', at, at, 1, VERSION))
        db.execute('INSERT INTO alert_audit(alert_id,action,actor,at) VALUES(?,?,?,?)', (aid, 'opened', 'collector', at))


def ingest(worker, sample):
    """Caller holds worker lock. Deduplicate repeated gateway reads and lifecycle cursors."""
    db = worker.db; now = time.time()
    previous = db.execute('SELECT value FROM security_meta WHERE key=?', ('last_collection',)).fetchone()
    previous_collection = float(previous['value']) if previous else None
    cursor = db.execute('SELECT value FROM security_meta WHERE key=?', ('lifecycle_cursor',)).fetchone()
    cursor = int(cursor['value']) if cursor else 0
    for event in db.execute('SELECT sequence,session_id,action,state,at FROM events WHERE sequence>? ORDER BY sequence LIMIT 500', (cursor,)).fetchall():
        cursor = event['sequence']
        if event['action'] not in ACTIONS or event['state'] not in STATES:
            continue
        kind = 'lifecycle_failure' if event['action'] == 'cleanup_incomplete' or event['state'] == 'failed' else 'lifecycle'
        detail = DETAILS[kind] if kind != 'lifecycle' else f"{event['action']}: {event['state']}"
        record(db, digest('lifecycle:' + str(cursor)), event['session_id'], kind, detail, float(event['at']))
    db.execute('INSERT OR REPLACE INTO security_meta VALUES(?,?)', ('lifecycle_cursor', str(cursor)))
    for event in sample.get('_decision_records', []):
        record(db, digest(event['session_id'] + ':' + event['fingerprint']), event['session_id'], 'egress_denied', DETAILS['egress_denied'], now)
    for session in sample.get('sessions', []):
        if not session.get('checks'):
            continue  # Missing data is unknown, never proof of recovery.
        active = any(c['status'] == 'fail' for c in session['checks'])
        key = session['id'] + ':policy_drift'
        previous = db.execute('SELECT * FROM security_conditions WHERE key=?', (key,)).fetchone()
        generation = previous['generation'] if previous else 0
        if active and (not previous or not previous['active']):
            generation += 1
            record(db, digest(key + ':' + str(generation)), session['id'], 'policy_drift', DETAILS['policy_drift'], now)
        db.execute('INSERT OR REPLACE INTO security_conditions VALUES(?,?,?)', (key, int(active), generation))
    from alert_rules import evaluate
    def emit(sid, kind, key, at):
        record(db, digest(key), sid, kind, DETAILS[kind], at)
    evaluate(worker, sample, now, previous_collection, emit)
    db.execute('DELETE FROM security_events WHERE observed_at<?', (now - RETENTION_SECONDS,))
    db.execute('DELETE FROM security_events WHERE id NOT IN (SELECT id FROM security_events ORDER BY id DESC LIMIT ?)', (MAX_EVENTS,))
    db.execute("DELETE FROM alert_audit WHERE alert_id IN (SELECT id FROM security_alerts WHERE status='resolved' AND resolved_at<?)", (now-RETENTION_SECONDS,))
    db.execute("DELETE FROM security_alerts WHERE status='resolved' AND resolved_at<?", (now-RETENTION_SECONDS,))
    db.execute('INSERT OR REPLACE INTO security_meta VALUES(?,?)', ('last_collection', str(now)))
    db.execute('INSERT OR REPLACE INTO security_meta VALUES(?,?)', ('collection_errors', str(sum(bool(s.get('error')) for s in sample.get('sessions', [])))))
    db.commit()


def ownership_filter(worker):
    if getattr(worker,'role','operator') == 'member':
        return 'session_id IN (SELECT id FROM sessions WHERE owner=?)', [worker.principal]
    return '', []


def history(worker, before=None, kind=None):
    scope, scope_args = ownership_filter(worker)
    clauses, args = ([scope] if scope else []), scope_args
    if before is not None:
        if not isinstance(before, int) or before <= 0:
            raise ValueError('invalid_history_cursor')
        clauses.append('id<?'); args.append(before)
    if kind is not None:
        if kind not in KINDS:
            raise ValueError('invalid_history_kind')
        clauses.append('kind=?'); args.append(kind)
    where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
    records = [dict(r) for r in worker.db.execute('SELECT id,observed_at,session_id,kind,detail,rules_version FROM security_events' + where + ' ORDER BY id DESC LIMIT 100', args)]
    return {'events': records, 'next_before': records[-1]['id'] if len(records) == 100 else None,
            'retention_days': 30, 'max_events': MAX_EVENTS}


def alerts(worker):
    scope, args = ownership_filter(worker)
    where = ' WHERE '+scope if scope else ''
    counts = {s: 0 for s in ('open', 'acknowledged', 'resolved')}
    for r in worker.db.execute('SELECT status,COUNT(*) n FROM security_alerts'+where+' GROUP BY status',args):
        counts[r['status']] = r['n']
    row = worker.db.execute('SELECT value FROM security_meta WHERE key=?', ('last_collection',)).fetchone()
    errors = worker.db.execute('SELECT value FROM security_meta WHERE key=?', ('collection_errors',)).fetchone()
    from alert_rules import BY_KIND, VERSION
    return {'rules_version': VERSION, 'collection_errors': (int(errors['value']) if errors else 0) if getattr(worker,'role','operator')=='operator' else None, 'alerts': [dict(r) | {'detail': DETAILS[r['kind']], 'scope': 'worker' if r['kind']=='collector_gap' else 'session', 'review': BY_KIND[r['kind']]['review'], 'trigger': BY_KIND[r['kind']]['trigger']} for r in worker.db.execute('SELECT * FROM security_alerts'+where+' ORDER BY last_seen DESC LIMIT 100',args)],
            'counts': counts, 'last_collection': float(row['value']) if row else None,
            'audit': [dict(r) for r in worker.db.execute('SELECT alert_id,action,actor,at FROM alert_audit WHERE alert_id IN (SELECT id FROM security_alerts'+where+') ORDER BY id DESC LIMIT 100',args)]}


def transition(worker, aid, action):
    if not re.fullmatch('[a-f0-9]{32}', aid) or action not in ('acknowledge', 'resolve'):
        raise ValueError('invalid_alert_action')
    row = worker.db.execute('SELECT * FROM security_alerts WHERE id=?', (aid,)).fetchone()
    if not row:
        raise ValueError('alert_not_found')
    if getattr(worker,'role','operator')=='member' and not worker.db.execute('SELECT 1 FROM sessions WHERE id=? AND owner=?',(row['session_id'],worker.principal)).fetchone():
        worker.denied('alert_access',aid)
        raise ValueError('alert_not_found')
    actor = 'local-operator' if getattr(worker,'principal','local-pilot')=='local-pilot' else 'principal:'+worker.principal
    status = 'acknowledged' if action == 'acknowledge' else 'resolved'
    if row['status'] == 'resolved' and status == 'acknowledged':
        raise ValueError('alert_already_resolved')
    if row['status'] != status:
        worker.db.execute('UPDATE security_alerts SET status=?,resolved_at=? WHERE id=?', (status, time.time() if status == 'resolved' else None, aid))
        worker.db.execute('INSERT INTO alert_audit(alert_id,action,actor,at) VALUES(?,?,?,?)', (aid, action, actor, time.time()))
        worker.db.commit()
    return {'id': aid, 'status': status, 'actor': actor}


def collect(worker):
    from console_observability import snapshot
    sample = snapshot(worker, include_telemetry=True, collect_decisions=True)
    with worker.locked():
        ingest(worker, sample)
    return {'collected': True}

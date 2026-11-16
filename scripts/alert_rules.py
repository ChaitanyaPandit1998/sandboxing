"""Versioned pilot review rules. Thresholds flag observations, never enforce session policy."""
import math

VERSION = 'pilot-review-v1'
WORKER_SUBJECT = '0' * 32
RULES = [
    {'kind':'policy_drift','name':'Policy configuration drift','severity':'high','trigger':'One failed selected configuration check; a verified recovery is required before a new episode.',
     'review':'Compare the failed check with approved policy. Inspect lifecycle events and confirm whether the change was authorized.'},
    {'kind':'lifecycle_failure','name':'Worker lifecycle failure','severity':'review','trigger':'A worker failure or incomplete cleanup event.',
     'review':'Inspect lifecycle state and remaining owned resources. Treat this as an operational failure until evidence supports another cause.'},
    {'kind':'egress_denied','name':'Egress denied','severity':'review','trigger':'One new deduplicated denied flow/stage observation.',
     'review':'Check whether the denial was expected validation or an application dependency. Do not expand the allowlist without policy review.'},
    {'kind':'egress_burst','name':'Repeated egress denials','severity':'high','trigger':'At least 5 distinct denied flow/stage observations collected within 5 minutes.',
     'review':'Review the session workload and expected destinations. Repeated retries or validation can cause this; it is not proof of an attack.'},
    {'kind':'resource_pressure','name':'Sustained resource pressure','severity':'review','trigger':'CPU >=90%, memory >=85%, or Docker PIDs >=112, in at least 3 consecutive valid samples spanning 60 seconds; sample gaps above 90 seconds reset the streak.',
     'review':'Inspect workload demand and the fixed limits. Distinguish ordinary builds/runtime overhead from unintended resource consumption.'},
    {'kind':'sample_unavailable','name':'Repeated incomplete samples','severity':'review','trigger':'At least 3 consecutive incomplete samples spanning 60 seconds; gaps above 90 seconds reset the streak.',
     'review':'Check Docker, gateway and session health. Missing telemetry is unknown, not a healthy or incident-free period.'},
    {'kind':'collector_gap','name':'Collector gap or clock change','severity':'review','trigger':'On collection resumption, the previous collection is over 90 seconds old, or its timestamp is in the future.',
     'review':'Check VM/Mac sleep, service availability and clock synchronization. Traffic may be missing from the sampled journal.'},
]
BY_KIND = {r['kind']: r for r in RULES}


def catalog():
    return {'version': VERSION, 'rules': RULES, 'enforcement':'review_only',
            'editable_in_ui': False, 'automatic_session_stop': False,
            'observation_scope':'Observed decisions and Docker samples; not complete traffic or process monitoring. Gateway backfill can group older traffic into one collection window.'}


def episode(db, key, active, sid, kind, now, emit):
    previous = db.execute('SELECT active,generation FROM security_conditions WHERE key=?', (key,)).fetchone()
    generation = previous['generation'] if previous else 0
    if active and (not previous or not previous['active']):
        generation += 1
        emit(sid, kind, key + ':' + str(generation), now)
    db.execute('INSERT OR REPLACE INTO security_conditions VALUES(?,?,?)', (key, int(active), generation))


def sustained(db, key, above, now):
    if above is None:
        db.execute('DELETE FROM rule_samples WHERE key=?', (key,))
        return None
    if not above:
        db.execute('DELETE FROM rule_samples WHERE key=?', (key,))
        return False
    old = db.execute('SELECT * FROM rule_samples WHERE key=?', (key,)).fetchone()
    if old and 0 < now - old['last_at'] <= 90:
        count, first = old['count'] + 1, old['first_at']
    elif old and now == old['last_at']:
        count, first = old['count'], old['first_at']
    else:
        count, first = 1, now
    db.execute('INSERT OR REPLACE INTO rule_samples VALUES(?,?,?,?)', (key, first, now, count))
    return count >= 3 and now - first >= 60


def evaluate(worker, sample, now, previous_collection, emit):
    db = worker.db
    if previous_collection is not None and (now - previous_collection > 90 or now < previous_collection):
        emit(WORKER_SUBJECT,'collector_gap',f'collector-gap:{previous_collection}:{now}',now)
    for session in sample.get('sessions', []):
        if session.get('state', 'ready') != 'ready':
            continue
        sid = session['id']
        count = db.execute("SELECT COUNT(*) FROM security_events WHERE session_id=? AND kind='egress_denied' AND observed_at>=? AND observed_at<=?", (sid, now-300, now)).fetchone()[0]
        episode(db, sid+':egress_burst', count >= 5, sid, 'egress_burst', now, emit)
        stats = session.get('telemetry') or {}
        def valid_number(value):
            return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>=0
        missing = bool(session.get('error')) or any(not valid_number(stats.get(k)) for k in ('cpu_percent','memory_percent','pids'))
        key = sid+':sample_unavailable'
        state = sustained(db,key,missing,now)
        if state is not None:
            # A sustained condition remains active until a valid recovery observation.
            if not missing or state:
                episode(db,key,state,sid,'sample_unavailable',now,emit)
        for metric,limit in [('cpu_percent',90),('memory_percent',85),('pids',112)]:
            value = (session.get('telemetry') or {}).get(metric)
            valid = isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>=0
            key = sid+':resource_pressure:'+metric
            above = value >= limit if valid else None
            state = sustained(db,key,above,now)
            if state is not None and (not above or state):
                episode(db,key,state,sid,'resource_pressure',now,emit)

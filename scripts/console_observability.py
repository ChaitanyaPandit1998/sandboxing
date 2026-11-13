"""Bounded, read-only monitoring for the trusted local pilot; no raw Docker/log data returned."""
import json
import hashlib
import re
import subprocess
import time

ALLOWED_HOSTS = ['auth.openai.com', 'chatgpt.com', 'api.openai.com']
REASONS = {'connect_authority', 'connect_tls_http_match'}


def decisions(lines):
    counts = {'allow': 0, 'deny': 0}
    reasons = {}
    for line in lines.splitlines():
        try:
            event = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(event, dict) or event.get('event') != 'tls_policy':
            continue
        decision, reason = event.get('decision'), event.get('reason')
        if decision in counts and reason in REASONS:
            counts[decision] += 1
            if decision == 'deny':
                reasons[reason] = reasons.get(reason, 0) + 1
    return {'counts': counts, 'deny_reasons': reasons}


def decision_records(sid, lines):
    records = []
    for line in lines.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict) or event.get('event') != 'tls_policy' or event.get('decision') != 'deny' or event.get('reason') not in REASONS:
            continue
        flow = event.get('flow_id')
        if not isinstance(flow, str) or not re.fullmatch('[a-f0-9-]{36}', flow):
            continue
        fingerprint = hashlib.sha256((flow + ':' + event['reason']).encode()).hexdigest()
        records.append({'session_id': sid, 'fingerprint': fingerprint})
    return records


def policy_checks(worker, sid, agent, gateway, network):
    host, config = agent.get('HostConfig', {}), agent.get('Config', {})
    options = host.get('SecurityOpt') or []
    mounts = agent.get('Mounts') or []
    expected_ca = str(worker.root / sid / 'ca.pem')
    mounts_ok = bool(mounts) and all(
        (m.get('Type') == 'volume' and m.get('Name') == worker.volume and m.get('Destination') == '/workspace')
        or (m.get('Type') == 'bind' and m.get('Source') == expected_ca and m.get('Destination') == '/trust/ca.pem' and not m.get('RW'))
        or (m.get('Type') == 'tmpfs' and m.get('Destination') in ('/tmp', '/home/agent')) for m in mounts)
    env = gateway.get('Config', {}).get('Env') or []
    approved = [v.split('=', 1)[1] for v in env if v.startswith('POC_ALLOWED_HOSTS=')]
    values = [
        ('Runtime', host.get('Runtime') == 'runsc-stable-20261109'),
        ('Non-root user', config.get('User') == '10001:10001'),
        ('Read-only root', host.get('ReadonlyRootfs') is True),
        ('No new privileges', any(v in ('no-new-privileges', 'no-new-privileges=true', 'no-new-privileges:true') for v in options)),
        ('Dropped capabilities', not host.get('Privileged') and 'ALL' in [v.upper() for v in host.get('CapDrop') or []] and not host.get('CapAdd')),
        ('Resource limits', host.get('NanoCpus') == 1000000000 and host.get('Memory') == 1073741824 and host.get('PidsLimit') == 128),
        ('Internal agent network', network.get('Internal') is True and set(agent.get('NetworkSettings', {}).get('Networks', {})) == {worker.names(sid)['internal']}),
        ('Workspace / CA mount boundary', mounts_ok and any(m.get('Destination') == '/workspace' for m in mounts) and any(m.get('Destination') == '/trust/ca.pem' for m in mounts)),
        ('Gateway domain configuration', len(approved) == 1 and set(approved[0].split(',')) == set(ALLOWED_HOSTS)),
    ]
    return [{'name': name, 'status': 'pass' if passed else 'fail'} for name, passed in values]


def snapshot(worker, include_telemetry=True, collect_decisions=False):
    rows = [dict(r) for r in worker.db.execute('SELECT * FROM sessions ORDER BY created DESC')]
    output = {'sampled_at': time.time(), 'policy_id': 'codex-tls-pilot-v1', 'allowed_hosts': ALLOWED_HOSTS,
              'domain_mode': 'default_deny', 'sessions': [], 'signals': [],
              'events': [dict(r) for r in worker.db.execute('SELECT session_id,action,state,at FROM events ORDER BY sequence DESC LIMIT 50')],
              'coverage': {'prompt_injection': 'not_implemented', 'malware_detection': 'not_implemented', 'central_alerts': 'not_implemented'},
              'log_scope': 'up to 200 log lines per active gateway from last 15 minutes; decisions, not unique requests; no blocked hostname capture',
              'telemetry_scope': 'current agent containers only; Docker CPU/memory/PIDs; no historical utilization or uptime SLO'}
    for row in rows:
        if row['state'] not in ('ready', 'provisioning', 'stopping'):
            continue
        sid = row['id']; names = worker.names(sid)
        item = {'id': sid, 'checks': [], 'telemetry': None, 'egress': None, 'error': None}
        try:
            agent = worker.exists('container', names['agent']); gateway = worker.exists('container', names['gateway']); network = worker.exists('network', names['internal'])
            worker.ensure_owned(agent, sid); worker.ensure_owned(gateway, sid); worker.ensure_owned(network, sid)
            item['checks'] = policy_checks(worker, sid, agent, gateway, network)
            if any(c['status'] == 'fail' for c in item['checks']):
                output['signals'].append({'session_id': sid, 'kind': 'policy_drift', 'severity': 'high', 'detail': 'Selected configuration differs from the approved pilot policy.'})
            if include_telemetry:
                stats = json.loads(worker.docker('stats', '--no-stream', '--format', '{{json .}}', names['agent']))
                cpu = stats.get('CPUPerc', ''); memory = stats.get('MemPerc', ''); pids = stats.get('PIDs', '')
                item['telemetry'] = {'cpu_percent': float(cpu[:-1]) if re.fullmatch(r'\d+(\.\d+)?%', cpu) else None,
                                     'memory_percent': float(memory[:-1]) if re.fullmatch(r'\d+(\.\d+)?%', memory) else None,
                                     'pids': int(pids) if re.fullmatch(r'\d+', pids) else None}
            logs = subprocess.run(['docker', 'logs', '--since', '15m', '--tail', '200', names['gateway']], capture_output=True, text=True, timeout=10)
            if logs.returncode == 0:
                item['egress'] = decisions(logs.stdout)
                if collect_decisions:
                    output.setdefault('_decision_records', []).extend(decision_records(sid, logs.stdout))
                if item['egress']['counts']['deny']:
                    output['signals'].append({'session_id': sid, 'kind': 'egress_denied', 'severity': 'review', 'detail': 'Gateway rejected sampled traffic; validation probes may also cause denials.'})
            else:
                item['error'] = 'gateway_decisions_unavailable'
        except Exception:
            item['error'] = 'sample_unavailable'
        output['sessions'].append(item)
    # Operational failures are review signals, not attribution of malicious behavior.
    for event in output['events']:
        if event['action'] == 'cleanup_incomplete' or event['state'] == 'failed':
            output['signals'].append({'session_id': event['session_id'], 'kind': 'lifecycle_failure', 'severity': 'review',
                                      'detail': 'Worker recorded an operational failure; inspect lifecycle events.', 'at': event['at']})
    output['signals'] = output['signals'][:50]
    return output

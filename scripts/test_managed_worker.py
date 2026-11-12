#!/usr/bin/env python3
"""Live synthetic worker checks inside the disposable Linux VM; no login/model use."""
import concurrent.futures
import importlib.util
import json
import pathlib
import subprocess
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('worker', ROOT / 'scripts/manage_codex_session.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def main():
    state = tempfile.mkdtemp(prefix='poc-worker-test-')
    worker = module.Worker(state)
    checks = {}
    timings = []
    try:
        with worker.locked():
            first = worker.create('persistence-first')
            again = worker.create('persistence-first')
        checks['idempotent_create'] = first['id'] == again['id']
        agent = worker.names(first['id'])['agent']
        worker.docker('exec', agent, 'sh', '-c', 'printf PERSISTED > /workspace/worker-test-marker; printf TEMPORARY > /home/agent/home-marker')
        obj = worker.exists('container', agent)
        checks['approved_runtime_policy'] = (obj['HostConfig']['Runtime'] == module.RUNTIME and obj['HostConfig']['ReadonlyRootfs']
                                              and obj['Config']['User'] == '10001:10001' and obj['HostConfig']['LogConfig']['Type'] == 'none')
        checks['managed_workspace_only'] = (any(m['Type'] == 'volume' and m['Destination'] == '/workspace' for m in obj['Mounts'])
                                            and not any(m['Destination'] == '/var/run/docker.sock' for m in obj['Mounts']))
        checks['ephemeral_home_and_public_ca_only'] = (
            '/home/agent' in obj['HostConfig']['Tmpfs'] and
            any(m['Destination'] == '/trust/ca.pem' and not m['RW'] for m in obj['Mounts']) and
            all(m['Destination'] != '/tmp/ca' for m in obj['Mounts']))
        node = r'''const http=require('http'),tls=require('tls'),fs=require('fs');
async function probe(host){return new Promise(resolve=>{const p=new URL(process.env.HTTPS_PROXY);
const req=http.request({host:p.hostname,port:p.port,method:'CONNECT',path:'api.openai.com:443',headers:{Host:'api.openai.com:443'}});
req.setTimeout(10000,()=>{req.destroy();resolve(0);});
req.on('connect',(r,socket)=>{if(r.statusCode!==200){socket.destroy();resolve(r.statusCode);return;}
const s=tls.connect({socket,servername:'api.openai.com',ca:fs.readFileSync('/trust/ca.pem'),rejectUnauthorized:true},()=>s.write('GET /v1/models HTTP/1.1\r\nHost: '+host+'\r\nConnection: close\r\n\r\n'));
s.setTimeout(10000,()=>{s.destroy();resolve(0);});s.once('data',b=>{resolve(Number(b.toString().split(' ')[1]));s.destroy();});s.on('error',()=>resolve(0));});req.on('error',()=>resolve(0));req.end();});}
(async()=>console.log(JSON.stringify({approved:await probe('api.openai.com'),mismatch:await probe('chatgpt.com')})))();'''
        network = json.loads(worker.docker('exec', agent, 'node', '-e', node))
        checks['verified_tls_provider_path'] = network['approved'] == 401
        checks['hostname_mismatch_denied'] = network['mismatch'] == 403
        with worker.locked():
            stopped = worker.stop(first['id'])
            repeated = worker.stop(first['id'])
            second = worker.create('persistence-second')
        checks['idempotent_stop'] = stopped == repeated
        agent = worker.names(second['id'])['agent']
        checks['workspace_persists'] = worker.docker('exec', agent, 'cat', '/workspace/worker-test-marker') == 'PERSISTED'
        checks['home_is_ephemeral'] = subprocess.run(['docker', 'exec', agent, 'test', '-e', '/home/agent/home-marker'], capture_output=True).returncode != 0
        with worker.locked():
            worker.stop(second['id'])

        def create(index):
            begin = time.monotonic()
            result = subprocess.run(['python3', str(ROOT / 'scripts/manage_codex_session.py'), '--state-dir', state,
                                     'create', '--key', f'capacity-{index}'], capture_output=True, text=True, timeout=180)
            elapsed = time.monotonic() - begin
            if result.returncode:
                raise RuntimeError(result.stderr)
            return json.loads(result.stdout), elapsed

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            starts = list(pool.map(create, range(5)))
        timings = [elapsed for _, elapsed in starts]
        checks['five_simultaneous_sessions'] = all(row['state'] == 'ready' for row, _ in starts)
        try:
            with worker.locked():
                worker.create('sixth-session')
            checks['sixth_session_denied'] = False
        except module.WorkerError as exc:
            checks['sixth_session_denied'] = str(exc) == 'quota_five_sessions'
        lost_id = starts[0][0]['id']
        worker.docker('rm', '-f', worker.names(lost_id)['gateway'])
        with worker.locked():
            worker.reconcile()
        checks['lost_gateway_reconciled'] = worker.get(lost_id)['state'] == 'failed' and worker.exists('container', worker.names(lost_id)['agent']) is None
        for row, _ in starts:
            with worker.locked():
                worker.stop(row['id'])
        # Simulate a worker dying after committing a provisioning reservation.
        sid = 'f' * 32
        worker.db.execute('INSERT INTO sessions(id,request_key,state,created) VALUES(?,?,?,?)', (sid, 'crash-fixture', 'provisioning', time.time()))
        worker.db.commit()
        names = worker.names(sid)
        worker.docker('network', 'create', '--internal', '--label', worker.label, '--label', f'poc.session={sid}', names['internal'])
        with worker.locked():
            worker.reconcile()
        checks['interrupted_provisioning_cleaned'] = worker.get(sid)['state'] == 'failed' and worker.exists('network', names['internal']) is None
        try:
            worker.get('../escape')
            checks['invalid_id_denied'] = False
        except module.WorkerError:
            checks['invalid_id_denied'] = True
        # A conflicting resource must be preserved, even when its name looks managed.
        foreign = worker.names('e' * 32)['internal']
        worker.docker('network', 'create', '--internal', '--label', 'poc.synthetic-foreign=true', foreign)
        try:
            try:
                worker.cleanup('e' * 32)
                checks['foreign_resource_preserved'] = False
            except module.WorkerError as exc:
                checks['foreign_resource_preserved'] = str(exc) == 'resource_ownership_mismatch' and worker.exists('network', foreign) is not None
        finally:
            worker.docker('network', 'rm', foreign)  # Created only by this test.
        denied = subprocess.run(['python3', str(ROOT / 'scripts/manage_codex_session.py'), '--state-dir', state,
                                 'create', '--image', 'unapproved'], capture_output=True)
        checks['arbitrary_image_override_denied'] = denied.returncode == 2
        events = worker.db.execute('SELECT action,state FROM events').fetchall()
        checks['lifecycle_events_recorded'] = bool(events) and any(r['action'] == 'create' for r in events)
    finally:
        for row in worker.db.execute('SELECT id FROM sessions').fetchall():
            with worker.locked():
                worker.stop(row['id'])
        volume = worker.exists('volume', worker.volume)
        if volume:
            worker.ensure_owned(volume)
            worker.docker('volume', 'rm', worker.volume)  # Synthetic test volume only.
    print(json.dumps({'passed': all(checks.values()), 'checks': checks,
                      'five_request_to_login_ready_seconds': timings,
                      'scope': 'trusted local worker CLI; cached images; unauthenticated; no browser/API/model'}, indent=2))
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == '__main__':
    main()

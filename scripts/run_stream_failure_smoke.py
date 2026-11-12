#!/usr/bin/env python3
"""Run inside Linux VM; synthetic streaming faults, no credentials or model calls."""
import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import time
import uuid


def command(args):
    return subprocess.check_output(args, text=True, timeout=40).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = pathlib.Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    root = pathlib.Path(__file__).resolve().parent.parent
    work = pathlib.Path(tempfile.mkdtemp(prefix='poc-stream-'))
    work.chmod(0o755)
    for name in ['server.py', 'route.py', 'client.py']:
        shutil.copyfile(root / 'tests/fixtures/stream_gateway' / name, work / name)
    shutil.copyfile(root / 'tls_gateway.py', work / 'tls_gateway.py')
    for p in work.iterdir():
        p.chmod(0o644)
    prefix = 'poc-stream-' + uuid.uuid4().hex[:10]
    gateway, client, network = prefix + '-gateway', prefix + '-client', prefix + '-net'
    image = 'mitmproxy/mitmproxy:12.3.1@sha256:2711066c855659b5af8b1dbb84494ed3eff69b42ece439c60b4fe09a2db829d4'
    summary = {}
    try:
        command(['docker', 'network', 'create', '--internal', network])
        command(['docker', 'run', '-d', '--name', gateway, '--network', network, '--user', '10001:10001',
                 '--read-only', '--tmpfs', '/tmp:size=64m,nosuid,nodev', '--cap-drop', 'ALL',
                 '--security-opt', 'no-new-privileges', '--cpus=1', '--memory=512m', '--pids-limit=128',
                 '-e', 'POC_ALLOWED_HOSTS=fixture.test', '-v', f'{work}:/fixture:ro',
                 '--entrypoint', 'python3', image, '/fixture/server.py'])
        cert = None
        for _ in range(40):
            result = subprocess.run(['docker', 'exec', gateway, 'cat', '/tmp/ca/mitmproxy-ca-cert.pem'], capture_output=True)
            if result.returncode == 0:
                cert = result.stdout
                break
            time.sleep(0.25)
        if not cert:
            raise RuntimeError('fixture startup failed: ' + command(['docker', 'logs', gateway]))
        (work / 'ca.pem').write_bytes(cert)
        (work / 'ca.pem').chmod(0o644)
        ip = json.loads(command(['docker', 'inspect', gateway]))[0]['NetworkSettings']['Networks'][network]['IPAddress']
        # Wait for the initial gateway listener, independently of CA generation.
        ready = ['docker', 'exec', gateway, 'python3', '-c',
                 'import socket;s=socket.create_connection(("127.0.0.1",3128),timeout=1);s.close()']
        for _ in range(40):
            if subprocess.run(ready, capture_output=True).returncode == 0:
                break
            time.sleep(0.25)
        else:
            raise RuntimeError('gateway listener failed: ' + command(['docker', 'logs', gateway]))
        metadata = {'scope': 'test-only loopback upstream routing; internal network; no model/auth; not production DNS/public-IP validation',
                    'gateway_image_id': command(['docker', 'image', 'inspect', image, '--format', '{{.Id}}']),
                    'client_image_id': command(['docker', 'image', 'inspect', 'local/gvisor-poc:latest', '--format', '{{.Id}}']),
                    'sources': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in work.glob('*.py')}}
        (output / 'environment.json').write_text(json.dumps(metadata, indent=2) + '\n')
        for runtime in ['runc', 'runsc-stable-20261109']:
            command(['docker', 'run', '-d', '--name', client, '--runtime', runtime, '--network', network,
                     '--user', '10001:10001', '--read-only', '--tmpfs', '/tmp:size=32m', '--cap-drop', 'ALL',
                     '--security-opt', 'no-new-privileges', '--memory=256m', '--pids-limit=128',
                     '-e', f'GATEWAY_IP={ip}', '-v', f'{work}:/fixture:ro', '-v', f'{work}/ca.pem:/trust/ca.pem:ro',
                     '--entrypoint', 'sleep', 'local/gvisor-poc:latest', 'infinity'])
            invoke = ['docker', 'exec', client, 'python3', '/fixture/client.py']
            suite = json.loads(command(invoke + ['suite']))
            interrupted = subprocess.Popen(invoke + ['interrupt'], stdout=subprocess.PIPE, text=True)
            for _ in range(100):
                if subprocess.run(['docker', 'exec', client, 'test', '-f', '/tmp/first-event'], capture_output=True).returncode == 0:
                    break
                time.sleep(0.1)
            else:
                interrupted.kill()
                raise RuntimeError('stream never started')
            kill = 'import os,signal;os.kill(int(open("/tmp/gateway.pid").read()),signal.SIGKILL)'
            command(['docker', 'exec', gateway, 'python3', '-c', kill])
            cut = json.loads(interrupted.communicate(timeout=10)[0])
            time.sleep(1)
            recovery = json.loads(command(invoke + ['normal']))
            pause = 'import os,signal;os.kill(int(open("/tmp/gateway.pid").read()),signal.SIGSTOP)'
            resume = pause.replace('SIGSTOP', 'SIGCONT')
            command(['docker', 'exec', gateway, 'python3', '-c', pause])
            try:
                unavailable = json.loads(command(invoke + ['normal']))
            finally:
                command(['docker', 'exec', gateway, 'python3', '-c', resume])
            after_resume = json.loads(command(invoke + ['normal']))
            checks = dict(suite['checks'])
            checks.update({'gateway_kill_interrupts_stream': bool(cut['events']) and not cut['done'],
                           'recovery_after_restart': recovery['done'],
                           'unavailable_fails_closed': not unavailable['done'] and not unavailable['events'] and unavailable['error'] is not None,
                           'recovery_after_resume': after_resume['done']})
            result = {'passed': all(checks.values()), 'checks': checks, 'suite': suite,
                      'interrupted': cut, 'restart_recovery': recovery, 'unavailable': unavailable, 'resume_recovery': after_resume}
            (output / f'{runtime}.json').write_text(json.dumps(result, indent=2) + '\n')
            summary[runtime] = {'passed': result['passed'], 'checks': len(checks)}
            command(['docker', 'rm', '-f', client])
            print(json.dumps({runtime: summary[runtime]}), flush=True)
        (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        if not all(s['passed'] for s in summary.values()):
            raise SystemExit(1)
    finally:
        for name in [client, gateway]:
            subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=20)
        subprocess.run(['docker', 'network', 'rm', network], capture_output=True, timeout=20)
        shutil.rmtree(work)


if __name__ == '__main__':
    main()

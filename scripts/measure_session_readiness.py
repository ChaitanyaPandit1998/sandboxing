#!/usr/bin/env python3
"""Measure cached-image, no-network sandbox readiness at bounded concurrency."""
import argparse
import concurrent.futures
import json
import math
import pathlib
import subprocess
import threading
import time
import uuid


def command(args, timeout=60):
    return subprocess.run(args, text=True, capture_output=True, timeout=timeout, check=True).stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', default='local/agent-session:claude-2.1.322-codex-0.167.1')
    parser.add_argument('--runtimes', nargs='+', default=['runc', 'runsc-stable-20261109'])
    parser.add_argument('--concurrency', type=int, default=5)
    parser.add_argument('--rounds', type=int, default=10)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if not 1 <= args.concurrency <= 5 or not 1 <= args.rounds <= 20:
        parser.error('this pilot runner permits concurrency 1–5 and rounds 1–20')
    output = pathlib.Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    image = json.loads(command(['docker', 'image', 'inspect', args.image]))[0]['Id']
    engine = json.loads(command(['docker', 'info', '--format', '{{json .}}']))
    for runtime in args.runtimes:
        if runtime not in engine['Runtimes']:
            parser.error(f'runtime not registered: {runtime}')
    metadata = {'image_id': image, 'concurrency': args.concurrency, 'rounds': args.rounds,
                'kernel': engine['KernelVersion'], 'cpus': engine['NCPU'], 'memory_bytes': engine['MemTotal'],
                'scope': 'cached image; network=none; container start + exec + workspace write + codex --version; no auth/model/API/attach',
                'limits': {'cpus': 1, 'memory': '1g', 'pids': 128}}
    (output / 'environment.json').write_text(json.dumps(metadata, indent=2) + '\n')
    run_id = uuid.uuid4().hex[:12]
    samples = []

    def start(runtime, round_number, index, barrier):
        name = f'poc-ready-{run_id}-{index}'
        row = {'runtime': runtime, 'round': round_number, 'slot': index, 'passed': False}
        barrier.wait()
        begin = time.monotonic()
        try:
            command(['docker', 'run', '-d', '--name', name, '--label', f'poc.readiness={run_id}',
                     '--pull=never', '--runtime', runtime, '--network=none', '--cpus=1', '--memory=1g',
                     '--pids-limit=128', '--read-only', '--tmpfs', '/tmp:size=128m,uid=10001,gid=10001',
                     '--tmpfs', '/home/agent:size=128m,uid=10001,gid=10001',
                     '--tmpfs', '/workspace:size=512m,uid=10001,gid=10001',
                     '--cap-drop=ALL', '--security-opt=no-new-privileges', '--user=10001:10001',
                     image, 'sleep', 'infinity'])
            row['container_started_seconds'] = time.monotonic() - begin
            row['cli'] = command(['docker', 'exec', name, 'sh', '-c',
                                  'test -w /workspace && touch /workspace/readiness-marker && codex --version'])
            row['ready_seconds'] = time.monotonic() - begin
            actual = json.loads(command(['docker', 'inspect', name]))[0]
            row['actual_runtime'] = actual['HostConfig']['Runtime']
            row['passed'] = row['actual_runtime'] == runtime and row['cli'].startswith('codex-cli ')
        except (subprocess.SubprocessError, OSError) as exc:
            row['error'] = str(exc)
            if isinstance(exc, subprocess.CalledProcessError):
                row['stderr'] = exc.stderr[:2000]
        finally:
            # Keep successful sessions alive until every slot finishes its readiness probe.
            barrier.wait(timeout=180)
            row['cleanup'] = subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=30).returncode == 0
        return row

    with (output / 'raw.jsonl').open('w') as raw:
        for round_number in range(args.rounds):
            runtimes = args.runtimes if round_number % 2 == 0 else list(reversed(args.runtimes))
            for runtime in runtimes:
                barrier = threading.Barrier(args.concurrency)
                with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
                    futures = [pool.submit(start, runtime, round_number, index, barrier) for index in range(args.concurrency)]
                    for future in futures:
                        row = future.result()
                        samples.append(row)
                        raw.write(json.dumps(row) + '\n')
                        raw.flush()
                print(f'{runtime} round {round_number + 1}/{args.rounds} complete', flush=True)
    summary = {}
    for runtime in args.runtimes:
        rows = [r for r in samples if r['runtime'] == runtime]
        values = sorted(r['ready_seconds'] for r in rows if r['passed'])
        summary[runtime] = {'attempts': len(rows), 'successes': len(values),
                            'cleanup_failures': sum(not r['cleanup'] for r in rows)}
        if values:
            summary[runtime].update({f'p{p}_seconds': values[math.ceil(len(values) * p / 100) - 1] for p in [50, 95]})
            summary[runtime]['max_seconds'] = max(values)
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))
    if any(not r['passed'] or not r['cleanup'] for r in samples):
        raise SystemExit(1)


if __name__ == '__main__':
    main()

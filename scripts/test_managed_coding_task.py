#!/usr/bin/env python3
"""Fixed authenticated coding task; save event timings/outcomes, never raw model/auth data."""
import argparse
import json
import os
import pathlib
import selectors
import subprocess
import time
import uuid
from manage_codex_session import Worker


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('session_id')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    worker = Worker('~/.local/state/gvisor-poc-worker')
    row = worker.get(args.session_id)
    if row['state'] != 'ready':
        raise SystemExit('ready_session_required')
    name = worker.names(args.session_id)['agent']
    status = subprocess.run(['docker', 'exec', name, 'codex', '--no-daemon', 'login', 'status'], capture_output=True, timeout=30)
    if status.returncode:
        raise SystemExit('private_login_required')
    directory = '/workspace/poc-coding-check-' + uuid.uuid4().hex[:12]
    worker.docker('exec', name, 'mkdir', directory)
    # Preflight the runtime required by the task before making a model request.
    worker.docker('exec', name, 'node', '--version')
    prompt = ('In this empty task directory, implement solution.cjs exporting sumEven(numbers), returning the sum of even integers from any iterable, including negative integers and generators. '
              'Write test_solution.test.cjs using node:test and node:assert/strict with at least four tests covering empty input, mixed values, negative values and a generator. '
              'Run node --test test_solution.test.cjs and fix any failures. Use only built-in Node modules, do not access the network, and keep all task files inside this directory. '
              'Finish with CODING_TASK_DONE when the tests pass.')
    command = ['docker', 'exec', name, 'codex', '--no-daemon', 'exec', '--sandbox', 'workspace-write',
               '--skip-git-repo-check', '--ephemeral', '--json', '--cd', directory, prompt]
    timings = {'first_event': None, 'first_response': None, 'first_tool': None, 'turn_completed': None}
    result = {'session_id': args.session_id, 'task_directory': directory, 'timings_seconds': timings,
              'error_events': 0, 'successful_command_events': 0, 'failed_command_events': 0,
              'tool_events': 0, 'timed_out': False}
    started = time.monotonic()
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    selector = selectors.DefaultSelector(); selector.register(process.stdout, selectors.EVENT_READ)
    buffer = b''

    def event_line(line):
        try:
            event = json.loads(line)
        except (ValueError, UnicodeDecodeError):
            return
        elapsed = round(time.monotonic() - started, 3)
        if timings['first_event'] is None:
            timings['first_event'] = elapsed
        kind = event.get('type')
        if kind in ('error', 'turn.failed'):
            result['error_events'] += 1
        if kind == 'turn.completed':
            timings['turn_completed'] = elapsed
        item = event.get('item') or {}
        if item.get('type') == 'agent_message' and item.get('text') and timings['first_response'] is None:
            timings['first_response'] = elapsed
        if item.get('type') in ('command_execution', 'file_change', 'mcp_tool_call'):
            result['tool_events'] += 1
            if timings['first_tool'] is None:
                timings['first_tool'] = elapsed
        if kind == 'item.completed' and item.get('type') == 'command_execution':
            if item.get('exit_code') == 0:
                result['successful_command_events'] += 1
            elif item.get('exit_code') is not None:
                result['failed_command_events'] += 1

    try:
        deadline = started + 240
        while selector.get_map():
            if time.monotonic() >= deadline:
                result['timed_out'] = True
                process.kill()
                break
            for key, _ in selector.select(timeout=1):
                chunk = os.read(key.fd, 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                buffer += chunk
                while b'\n' in buffer:
                    line, buffer = buffer.split(b'\n', 1)
                    event_line(line)
                if len(buffer) > 1024 * 1024:
                    result['oversized_event'] = True
                    process.kill()
                    break
        if buffer and not result.get('oversized_event'):
            event_line(buffer)
        try:
            result['exit_code'] = process.wait(timeout=max(1, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            result['timed_out'] = True
            process.kill(); result['exit_code'] = process.wait(timeout=10)
    finally:
        selector.close(); process.stdout.close()
    timings['process_completed'] = round(time.monotonic() - started, 3)
    if result['exit_code'] == 0 and not result['timed_out']:
        # Independent oracle executes only generated code inside the same restricted container.
        oracle = r'''const fs=require('node:fs'),assert=require('node:assert/strict'),cp=require('node:child_process');
assert(fs.statSync('solution.cjs').isFile());assert(fs.statSync('test_solution.test.cjs').isFile());
const {sumEven:f}=require('./solution.cjs');
assert.equal(f([]),0);assert.equal(f([1,2,3,4,5,6]),12);assert.equal(f([-8,-3,-2,1,4]),-6);
function* seq(){for(let i=-10;i<=10;i++)yield i;}assert.equal(f(seq()),0);assert.equal(f([7,7,7]),0);
const p=cp.spawnSync(process.execPath,['--test','--test-reporter=tap','test_solution.test.cjs'],{encoding:'utf8',timeout:20000});
assert.equal(p.status,0);const m=p.stdout.match(/# tests (\d+)/);assert(m && Number(m[1])>=4);
'''
        verify = subprocess.run(['docker', 'exec', '-w', directory, name, 'node', '-e', oracle], capture_output=True, timeout=30)
        result['independent_code_and_tests_passed'] = verify.returncode == 0
    else:
        result['independent_code_and_tests_passed'] = False
    result['passed'] = (result['exit_code'] == 0 and not result['timed_out'] and not result['error_events']
                        and timings['turn_completed'] is not None and result['successful_command_events'] > 0
                        and result['independent_code_and_tests_passed'])
    result['scope'] = 'one authenticated coding task; existing logged-in session; event-observation timings, not token-level TTFT; excludes provisioning/manual login; no p95 or uptime claim'
    pathlib.Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    worker.db.close()
    if not result['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()

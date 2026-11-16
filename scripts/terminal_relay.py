"""Bounded memory-only HTTP/PTY relay for the trusted local personal pilot."""
import base64
import fcntl
import hashlib
import os
import pty
import re
import secrets
import select
import struct
import subprocess
import sys
import termios
import threading
import time
import uuid
from pathlib import Path


class TerminalError(RuntimeError):
    pass


def dimensions(cols, rows):
    if type(cols) is not int or type(rows) is not int or not 20 <= cols <= 300 or not 5 <= rows <= 120:
        raise TerminalError('invalid_terminal_size')
    return cols, rows


class PtyChannel:
    limit = 256 * 1024

    def __init__(self, adapter, sid, mode, cols, rows, expires, clock=time.monotonic):
        self.id, self.relay_id = secrets.token_urlsafe(32), uuid.uuid4().hex
        self.adapter, self.sid, self.mode = adapter, sid, mode
        self.clock, self.last_seen, self.expires = clock, clock(), expires
        self.lock = threading.RLock()
        self.buffer, self.base = bytearray(), 0
        self.closed, self.reason, self.cleanup = False, None, 'not_required'
        self.next_check = self.clock() + 5
        master, slave = pty.openpty()
        try:
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0))
            env = {key: os.environ[key] for key in ('PATH','HOME','USER','LOGNAME','TMPDIR','LIMA_HOME') if key in os.environ}
            env.update(TERM='xterm-256color', LANG='en_US.UTF-8', SSH=str(Path(__file__).with_name('terminal_ssh.sh')))
            command = adapter.terminal_command(sid, mode, self.relay_id)
            self.process = subprocess.Popen([sys.executable, str(Path(__file__).with_name('terminal_exec.py')), *command],
                stdin=slave, stdout=slave, stderr=slave, env=env, start_new_session=True, close_fds=True)
        except Exception:
            os.close(master)
            raise
        finally:
            os.close(slave)
        self.fd = master
        os.set_blocking(master, False)
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _read(self):
        try:
            while not self.closed:
                if self.clock() - self.last_seen > 30 or time.time() >= self.expires:
                    self.close('expired' if time.time() >= self.expires else 'disconnected')
                    break
                try:
                    ready, _, _ = select.select([self.fd], [], [], .2)
                except (OSError, ValueError):
                    break
                if ready:
                    try:
                        with self.lock:
                            if self.closed:
                                break
                            data = os.read(self.fd, 16384)
                    except BlockingIOError:
                        continue
                    except OSError:
                        break
                    if not data:
                        break
                    with self.lock:
                        if self.closed:
                            break
                        self.buffer.extend(data)
                        if len(self.buffer) > self.limit:
                            drop = len(self.buffer) - self.limit
                            del self.buffer[:drop]
                            self.base += drop
                elif self.process.poll() is not None:
                    break
        finally:
            self.close('process_exited', preserve_output=True)

    def close(self, reason='disconnected', preserve_output=False):
        with self.lock:
            if self.closed:
                if not preserve_output:
                    self.buffer.clear()
                return
            self.closed, self.reason, self.closed_at, self.cleanup = True, reason, self.clock(), 'pending'
            if not preserve_output:
                self.buffer.clear()
            try:
                os.close(self.fd)
            except OSError:
                pass
        # Closing the controlling PTY sends HUP; reap the child without blocking HTTP.
        threading.Thread(target=self._finish, daemon=True).start()

    def _finish(self):
        local_done = False
        try:
            if self.process.poll() is None:
                self.process.terminate()
            try:
                self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
            local_done = self.process.poll() is not None
        except (OSError, subprocess.SubprocessError):
            local_done = self.process.poll() is not None
        try:
            result = self.adapter.run('close-terminal', self.sid, '--terminal-id', self.relay_id)
            self.cleanup = 'complete' if local_done and result.get('closed') is True else 'failed'
        except Exception:
            self.cleanup = 'failed'

    def output(self, cursor):
        with self.lock:
            if type(cursor) is not int or not self.base <= cursor <= self.base + len(self.buffer):
                self.close('output_overrun')
                raise TerminalError('terminal_output_unavailable')
            data = bytes(self.buffer[cursor-self.base:cursor-self.base+32768])
            self.last_seen = self.clock()
            return {'data': base64.b64encode(data).decode(), 'cursor': cursor+len(data),
                    'closed': self.closed, 'reason': self.reason, 'cleanup': self.cleanup}

    def input(self, encoded):
        if not isinstance(encoded, str) or not 0 < len(encoded) <= 5500:
            raise TerminalError('invalid_terminal_input')
        try:
            data = base64.b64decode(encoded, validate=True)
        except ValueError:
            raise TerminalError('invalid_terminal_input') from None
        if not 0 < len(data) <= 4096:
            raise TerminalError('invalid_terminal_input')
        with self.lock:
            if self.closed or time.time() >= self.expires:
                self.close('expired')
                raise TerminalError('terminal_closed')
            self.last_seen = self.clock()
            try:
                if not select.select([], [self.fd], [], .1)[1]:
                    raise TerminalError('terminal_input_busy')
                written = os.write(self.fd, data)
                if written != len(data):
                    self.close('input_overrun')
                    raise TerminalError('terminal_input_busy')
            except OSError:
                raise TerminalError('terminal_closed') from None

    def resize(self, cols, rows):
        dimensions(cols, rows)
        with self.lock:
            if self.closed:
                raise TerminalError('terminal_closed')
            try:
                fcntl.ioctl(self.fd, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0))
            except OSError:
                raise TerminalError('terminal_closed') from None


class TerminalRelay:
    capacity, ticket_seconds = 5, 30

    def __init__(self, channel_factory=PtyChannel, clock=time.monotonic):
        self.channel_factory, self.clock = channel_factory, clock
        self.tickets, self.channels, self.reservations = {}, {}, set()
        self.lock, self.stop = threading.RLock(), threading.Event()
        self.watch = threading.Thread(target=self._watch, daemon=True)
        self.watch.start()

    @staticmethod
    def owner(adapter, browser):
        if not re.fullmatch(r'[A-Za-z0-9_-]{43}', browser):
            raise TerminalError('terminal_browser_required')
        return (adapter.principal, hashlib.sha256(browser.encode()).hexdigest())

    @staticmethod
    def authorize(adapter, sid):
        row = adapter.run('authorize-attach', sid)
        # Defense in depth: operator metadata scope never becomes foreign credential access.
        if row.get('owner') != adapter.principal:
            raise TerminalError('attach_owner_required')
        if row.get('state') != 'ready' or (row.get('expires') is not None and row['expires'] <= time.time()):
            raise TerminalError('session_not_ready')
        return row

    def issue(self, adapter, browser, sid, mode):
        if not re.fullmatch('[a-f0-9]{32}', sid) or mode not in ('login', 'attach'):
            raise TerminalError('invalid_terminal_request')
        owner = self.owner(adapter, browser)
        self.authorize(adapter, sid)
        token = secrets.token_urlsafe(32)
        with self.lock:
            self._prune()
            if len(self.tickets) >= 32:
                raise TerminalError('terminal_capacity')
            self.tickets[hashlib.sha256(token.encode()).hexdigest()] = (owner, sid, mode, self.clock()+self.ticket_seconds)
        return {'ticket': token, 'expires_in': self.ticket_seconds}

    def connect(self, adapter, browser, token, cols, rows):
        owner = self.owner(adapter, browser)
        dimensions(cols, rows)
        if not isinstance(token, str) or not re.fullmatch('[A-Za-z0-9_-]{43}', token):
            raise TerminalError('terminal_ticket_invalid')
        with self.lock:
            self._prune()
            ticket = self.tickets.pop(hashlib.sha256(token.encode()).hexdigest(), None)
            if not ticket or ticket[0] != owner or ticket[3] <= self.clock():
                raise TerminalError('terminal_ticket_invalid')
            _, sid, mode, _ = ticket
            active = [ch for ch, _ in self.channels.values() if not ch.closed or ch.cleanup != 'complete']
            if len(active)+len(self.reservations) >= self.capacity or sid in self.reservations or any(ch.sid==sid for ch in active):
                raise TerminalError('terminal_capacity')
            self.reservations.add(sid)
        try:
            row = self.authorize(adapter, sid)  # Recheck after ticket issue and before starting PTY.
            channel = self.channel_factory(adapter, sid, mode, cols, rows, row.get('expires') or time.time()+3600)
            with self.lock:
                self.channels[channel.id] = (channel, owner)
            return {'id': channel.id, 'transport': 'bounded_http_pty', 'cursor': 0}
        finally:
            with self.lock:
                self.reservations.discard(sid)

    def get(self, adapter, browser, cid):
        owner = self.owner(adapter, browser)
        with self.lock:
            self._prune()
            item = self.channels.get(cid)
            if item is None or item[1] != owner:
                raise TerminalError('terminal_not_found')
            return item[0]

    def revoke_session(self, sid):
        with self.lock:
            self.tickets = {k:v for k,v in self.tickets.items() if v[1] != sid}
            for channel, _ in self.channels.values():
                if channel.sid == sid:
                    channel.close('session_stopped')

    def _prune(self):
        now = self.clock()
        self.tickets = {k:v for k,v in self.tickets.items() if v[3] > now}
        for cid, (channel, _) in list(self.channels.items()):
            if channel.closed and now-channel.closed_at > 5:
                channel.buffer.clear()
                if channel.cleanup == 'complete':
                    del self.channels[cid]

    def _watch(self):
        while not self.stop.wait(1):
            with self.lock:
                self._prune()
                channels = [ch for ch,_ in self.channels.values()]
            for ch in channels:
                if ch.closed:
                    if ch.cleanup == 'failed' and self.clock() >= ch.next_check:
                        ch.next_check = self.clock()+5
                        ch.cleanup = 'pending'
                        threading.Thread(target=ch._finish, daemon=True).start()
                    continue
                if ch.clock()-ch.last_seen > 30 or time.time() >= ch.expires:
                    ch.close('expired' if time.time() >= ch.expires else 'disconnected')
                elif self.clock() >= ch.next_check:
                    ch.next_check = self.clock()+5
                    try:
                        self.authorize(ch.adapter, ch.sid)
                    except Exception:
                        ch.close('session_unavailable')

    def close(self):
        self.stop.set()
        with self.lock:
            self.tickets.clear()
            for channel,_ in self.channels.values():
                channel.close('server_stopped')
        self.watch.join(timeout=1)
        deadline = time.monotonic()+4
        while time.monotonic()<deadline and any(ch.cleanup=='pending' for ch,_ in self.channels.values()):
            time.sleep(.05)

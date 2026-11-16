#!/usr/bin/env python3
"""Acquire the slave PTY as controlling terminal after safe subprocess exec."""
import fcntl
import os
import sys
import termios

if __name__ == '__main__':
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)
    os.execvpe(sys.argv[1], sys.argv[1:], os.environ)

"""Block and count outbound network connections while an adapter runs.

Loopback is allowed (some frameworks use local sockets for event loops). Anything else raises, and the
attempt is counted, so "runs offline" is measured rather than assumed.
"""

from __future__ import annotations

import socket
from contextlib import contextmanager

_LOCAL = ("127.", "::1", "localhost")


@contextmanager
def no_network():
    attempts: list[str] = []
    orig_connect, orig_cx = socket.socket.connect, socket.create_connection
    orig_gai = socket.getaddrinfo

    def connect(self, address):
        host = str(address[0]) if isinstance(address, tuple) else str(address)
        if self.family == socket.AF_UNIX or host.startswith(_LOCAL):
            return orig_connect(self, address)
        attempts.append(host)
        raise OSError(f"network blocked in bakeoff: {host}")

    def gai(host, *a, **kw):
        if host is None or str(host).startswith(_LOCAL):
            return orig_gai(host, *a, **kw)
        attempts.append(str(host))
        raise socket.gaierror(f"dns blocked in bakeoff: {host}")

    socket.socket.connect = connect
    socket.getaddrinfo = gai
    try:
        yield attempts
    finally:
        socket.socket.connect, socket.create_connection, socket.getaddrinfo = orig_connect, orig_cx, orig_gai

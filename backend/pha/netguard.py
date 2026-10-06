"""Opt-in runtime network guard (PHA_NET_GUARD=1): refuse and log every non-loopback connection.

Installed from `pha/__init__.py` before any other library is imported, so it also covers
telemetry or model-hub calls made by dependencies at import time. Each blocked attempt is logged
and, if PHA_NET_GUARD_LOG is set, appended to that file as one JSON line. The privacy test
asserts that this file stays empty for a full upload → chat → delete session.
"""

import json
import logging
import os
import socket
import threading
import time

from pha.offline import is_loopback_host

log = logging.getLogger(__name__)
_lock = threading.Lock()
_installed = False


class BlockedConnection(ConnectionRefusedError):
    """Raised instead of opening a connection to a non-loopback address."""


def _record(kind: str, destination: str) -> None:
    log.error("Network guard blocked %s to %s", kind, destination)
    path = os.environ.get("PHA_NET_GUARD_LOG")
    if path:
        line = json.dumps({"time": time.time(), "kind": kind, "destination": destination})
        with _lock, open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def _allowed(host: object) -> bool:
    # Bind-all (None / "") is a listen address, not an outbound destination.
    if host in (None, "", b""):
        return True
    return is_loopback_host(host.decode() if isinstance(host, bytes) else str(host))


def _check(kind: str, address: object) -> None:
    if isinstance(address, tuple) and address and not _allowed(address[0]):
        destination = f"{address[0]}:{address[1]}" if len(address) > 1 else str(address[0])
        _record(kind, destination)
        raise BlockedConnection(f"network guard: outbound connection to {destination} blocked")


def install() -> None:
    """Patch socket connect/connect_ex/sendto and name resolution. Idempotent."""
    global _installed
    if _installed:
        return
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_sendto = socket.socket.sendto
    real_getaddrinfo = socket.getaddrinfo

    def connect(self, address):
        _check("connect", address)
        return real_connect(self, address)

    def connect_ex(self, address):
        _check("connect", address)
        return real_connect_ex(self, address)

    def sendto(self, data, *args):
        _check("sendto", args[-1])
        return real_sendto(self, data, *args)

    def getaddrinfo(host, port, *args, **kwargs):
        # Resolving a public name is the first step of any outbound call; refuse it early so
        # the destination's name (not just an IP) appears in the log.
        if not _allowed(host):
            _check("resolve", (host, port))
        return real_getaddrinfo(host, port, *args, **kwargs)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.socket.sendto = sendto
    socket.getaddrinfo = getaddrinfo
    _installed = True
    if path := os.environ.get("PHA_NET_GUARD_LOG"):
        open(path, "a").close()  # an existing (empty) log shows the guard was active
    log.info("Network guard enabled: non-loopback connections are blocked")


def install_from_env() -> None:
    if os.environ.get("PHA_NET_GUARD", "").strip() == "1":
        install()

"""Restrictions installed in a worker process before any bot code is loaded.

Best effort, for good-faith bots: sockets and subprocesses raise
PermissionError, and a memory rlimit is set where the OS enforces one (Linux;
macOS ignores RLIMIT_AS). Bot output is captured per bot, keeping the first
lines for the report.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys

_PROCESS_FUNCS = ("system", "popen", "fork", "forkpty", "execv", "execve", "execl", "execle",
                  "execlp", "execlpe", "execvp", "execvpe", "spawnl", "spawnle", "spawnlp",
                  "spawnlpe", "spawnv", "spawnve", "spawnvp", "spawnvpe", "posix_spawn", "posix_spawnp")


def _no_network(*args, **kwargs):
    raise PermissionError("bots may not use the network")


def _no_process(*args, **kwargs):
    raise PermissionError("bots may not start processes")


class _NoSocket(socket.socket):
    def __init__(self, *args, **kwargs):
        _no_network()


def install_guards(memory_mb: int | None = None) -> list[str]:
    """Install the restrictions; return notes about any that couldn't be applied."""
    import _socket

    notes = []
    socket.socket = _NoSocket
    _socket.socket = _NoSocket
    for name in ("create_connection", "create_server", "socketpair", "fromfd", "getaddrinfo"):
        setattr(socket, name, _no_network)
    subprocess.Popen = _no_process
    for name in _PROCESS_FUNCS:
        if hasattr(os, name):
            setattr(os, name, _no_process)
    if memory_mb and sys.platform == "darwin":
        notes.append("memory limit not applied: macOS doesn't enforce RLIMIT_AS")
    elif memory_mb:
        try:
            import resource
            limit = memory_mb * 2**20
            resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
        except (ImportError, ValueError, OSError) as e:
            notes.append(f"memory limit not applied: {e}")
    return notes


class Capture:
    """Stand-in for stdout/stderr during bot calls: keeps the first ``keep``
    lines (truncated) and counts the rest."""

    def __init__(self, keep: int = 20, width: int = 300):
        self.keep, self.width = keep, width
        self.lines: list[str] = []
        self.dropped = 0
        self._partial = ""

    def write(self, text: str) -> int:
        if not isinstance(text, str):
            text = str(text)
        chunks = (self._partial + text).split("\n")
        self._partial = chunks.pop()[: self.width]
        for line in chunks:
            if len(self.lines) < self.keep:
                self.lines.append(line[: self.width])
            else:
                self.dropped += 1
        return len(text)

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return False

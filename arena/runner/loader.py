"""Loading a bot package under a unique module name.

Several bots share one process, so each is imported as its own top-level
package (``bot_<hash>``) and must use relative imports for its own modules.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import os
import sys
import types


def _files(path: str) -> list[str]:
    out = []
    for root, dirs, files in os.walk(path):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__" and not d.startswith("."))
        out += [os.path.join(root, f) for f in sorted(files) if not f.endswith((".pyc", ".pyo"))]
    return out


def bot_size(path: str) -> int:
    return sum(os.path.getsize(f) for f in _files(path))


def bot_hash(path: str) -> str:
    """sha256 over relative file names and contents; identifies a snapshot."""
    h = hashlib.sha256()
    for f in _files(path):
        h.update(os.path.relpath(f, path).encode() + b"\0")
        with open(f, "rb") as fh:
            h.update(fh.read())
        h.update(b"\0")
    return h.hexdigest()


def module_name_for(path: str) -> str:
    return "bot_" + hashlib.sha256(os.path.abspath(path).encode()).hexdigest()[:16]


def load_bot(path: str, module_name: str | None = None) -> type:
    """Import ``path`` as a package and return its ``agent.Agent`` class."""
    path = os.path.abspath(path)
    if not os.path.isfile(os.path.join(path, "agent.py")):
        raise ImportError(f"{path} has no agent.py")
    name = module_name or module_name_for(path)
    init = os.path.join(path, "__init__.py")
    if os.path.isfile(init):
        spec = importlib.util.spec_from_file_location(name, init, submodule_search_locations=[path])
        pkg = importlib.util.module_from_spec(spec)
        sys.modules[name] = pkg
        try:
            spec.loader.exec_module(pkg)
        except BaseException:
            sys.modules.pop(name, None)
            raise
    else:
        pkg = types.ModuleType(name)
        pkg.__path__ = [path]
        pkg.__package__ = name
        sys.modules[name] = pkg
    try:
        mod = importlib.import_module(name + ".agent")
    except BaseException:
        for key in [k for k in sys.modules if k == name or k.startswith(name + ".")]:
            del sys.modules[key]
        raise
    agent = getattr(mod, "Agent", None)
    if not isinstance(agent, type):
        raise ImportError(f"{path}/agent.py defines no class Agent")
    return agent

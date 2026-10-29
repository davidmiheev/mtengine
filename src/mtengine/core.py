"""Process runner, result cache with provenance, tool versions, background jobs."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from . import __version__

CACHE_DIR = Path(os.environ.get("MTENGINE_CACHE", Path.home() / ".cache" / "mtengine"))
ELAN_BIN = Path.home() / ".elan" / "bin"


class EngineError(RuntimeError):
    """A backend failed; the message carries the tail of its output."""


@dataclass
class Run:
    returncode: int
    stdout: str
    stderr: str
    seconds: float


def tool_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PATH"] = f"{ELAN_BIN}:{env.get('PATH', '')}"
    return env


def run_process(cmd: list[str], *, files: dict[str, str] | None = None, stdin: str | None = None,
                cwd: str | Path | None = None, timeout: float = 600) -> tuple[Run, Path]:
    """Run `cmd` with `files` written into a fresh temporary directory.

    The literal string "{dir}" in any argument is replaced by that directory. If `cwd` is not
    given, the command runs inside it. Returns the run and the (already deleted) directory path.
    """
    with tempfile.TemporaryDirectory(prefix="mte-") as d:
        for name, content in (files or {}).items():
            (Path(d) / name).write_text(content)
        argv = [a.replace("{dir}", d) for a in cmd]
        t = time.time()
        try:
            p = subprocess.run(argv, input=stdin if stdin is not None else "", capture_output=True, text=True,
                               cwd=str(cwd) if cwd else d, timeout=timeout, env=tool_env())
        except subprocess.TimeoutExpired as e:
            raise EngineError(f"{argv[0]} timed out after {timeout}s") from e
        return Run(p.returncode, p.stdout, p.stderr, time.time() - t), Path(d)


def tail(text: str, n: int = 25) -> str:
    return "\n".join(text.strip().splitlines()[-n:])


_VERSION_CMDS = {
    "macaulay2": (["M2", "--version"], 0),
    "gfan": (["gfan", "_version"], 1),
    "polymake": (["polymake", "--version"], 0),
    "singular": (["Singular", "--version"], 0),
    "nauty": (["dreadnaut", "--version"], 0),
    "python": (["python3", "--version"], 0),
}


@lru_cache(maxsize=None)
def tool_version(tool: str) -> str:
    """Version string of a backend (cached for the life of the process)."""
    if tool == "lean":
        from .backends import lean
        return lean.version()
    if tool == "regina":
        from .backends import regina
        return regina.version()
    if tool == "engine":
        return __version__
    cmd, line = _VERSION_CMDS[tool]
    if not shutil.which(cmd[0]):
        return "MISSING"
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=tool_env(),
                           stdin=subprocess.DEVNULL)
    except Exception:  # noqa: BLE001 - report, don't fail
        return "UNAVAILABLE"
    lines = [l.strip() for l in (p.stdout + p.stderr).splitlines() if l.strip()]
    return lines[line] if len(lines) > line else (lines[0] if lines else "unknown")


def cached(backend: str, fn: str, payload: dict[str, Any], compute: Callable[[], Any],
           use_cache: bool = True) -> dict[str, Any]:
    """Return {"value", "provenance", "cached"}; compute and store on a miss.

    The cache key covers the backend, its version, the engine version, the function and its
    input, so upgrading a tool invalidates its results instead of silently reusing them.
    """
    key_obj = {"backend": backend, "version": tool_version(backend), "engine": __version__,
               "fn": fn, "input": payload}
    key = hashlib.sha256(json.dumps(key_obj, sort_keys=True, default=str).encode()).hexdigest()
    path = CACHE_DIR / key[:2] / f"{key}.json"
    if use_cache and path.exists():
        rec = json.loads(path.read_text())
        rec["cached"] = True
        return rec
    t = time.time()
    value = compute()
    rec = {"value": value,
           "provenance": {"backend": backend, "backend_version": key_obj["version"],
                          "engine_version": __version__, "function": fn, "input_sha256": key,
                          "seconds": round(time.time() - t, 3),
                          "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(rec, default=str))
    tmp.replace(path)
    rec["cached"] = False
    return rec


# ---------------------------------------------------------------- background jobs
_EXECUTOR = ThreadPoolExecutor(max_workers=int(os.environ.get("MTENGINE_WORKERS", "2")))
_JOBS: dict[str, dict[str, Any]] = {}
_LOCK = threading.Lock()


def submit(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> str:
    job_id = uuid.uuid4().hex[:12]
    with _LOCK:
        _JOBS[job_id] = {"state": "queued", "submitted": time.time()}

    def work():
        with _LOCK:
            _JOBS[job_id]["state"] = "running"
        try:
            result = fn(*args, **kwargs)
            update = {"state": "done", "result": result}
        except Exception as e:  # noqa: BLE001 - reported to the caller
            update = {"state": "error", "error": f"{type(e).__name__}: {e}",
                      "traceback": tail(traceback.format_exc(), 15)}
        with _LOCK:
            _JOBS[job_id].update(update, finished=time.time())

    _EXECUTOR.submit(work)
    return job_id


def job_status(job_id: str) -> dict[str, Any]:
    with _LOCK:
        if job_id not in _JOBS:
            raise EngineError(f"unknown job {job_id}")
        return dict(_JOBS[job_id])

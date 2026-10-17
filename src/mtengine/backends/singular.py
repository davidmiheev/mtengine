"""Singular adapter."""
from __future__ import annotations

from ..core import EngineError, run_process, tail


def run(code: str, timeout: float = 600) -> str:
    """Run Singular code (quiet mode); return standard output."""
    r, _ = run_process(["Singular", "-q", "--no-rc"], stdin=code.rstrip() + "\nquit;\n", timeout=timeout)
    if r.returncode != 0 or "? " in r.stdout:
        raise EngineError(f"Singular failed (exit {r.returncode}):\n{tail(r.stdout + r.stderr)}")
    return r.stdout

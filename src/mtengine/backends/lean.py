"""Lean 4 / Mathlib adapter: compile a source file inside the project and report axioms."""
from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

from ..core import EngineError, run_process, tail

PROJECT = Path(os.environ.get("MTENGINE_LEAN_PROJECT",
                              Path(__file__).resolve().parents[4] / "formal"))


def version() -> str:
    if not (PROJECT / "lean-toolchain").exists():
        return "MISSING (no Lean project at MTENGINE_LEAN_PROJECT)"
    r, _ = run_process(["lean", "--version"], cwd=PROJECT, timeout=120)
    mathlib = ""
    manifest = PROJECT / "lake-manifest.json"
    if manifest.exists():
        import json
        for pkg in json.loads(manifest.read_text()).get("packages", []):
            if pkg.get("name") == "mathlib":
                mathlib = f"; mathlib {pkg.get('rev', '')[:8]}"
    return (r.stdout.strip().splitlines() or ["unknown"])[0] + mathlib


def check(source: str, theorems: list[str] | None = None, timeout: float = 3600) -> dict:
    """Compile `source` with `lake env lean` in the project; print the axioms of `theorems`.

    ok is True iff Lean reports no errors. A theorem relying on `sorry` shows `sorryAx`
    among its axioms and is reported in `uses_sorry`.
    """
    theorems = theorems or []
    body = source.rstrip() + "\n" + "".join(f"\n#print axioms {t}" for t in theorems) + "\n"
    name = f"MteCheck_{uuid.uuid4().hex[:8]}.lean"
    path = PROJECT / ".lake" / "mte" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    try:
        r, _ = run_process(["lake", "env", "lean", str(path)], cwd=PROJECT, timeout=timeout)
    finally:
        path.unlink(missing_ok=True)
    out = (r.stdout + r.stderr).replace(str(path), name)
    errors = [l for l in out.splitlines() if ": error" in l]
    axioms = {}
    for t in theorems:
        m = re.search(rf"'{re.escape(t)}' depends on axioms: \[([^\]]*)\]", out)
        if m:
            axioms[t] = [a.strip() for a in m.group(1).split(",") if a.strip()]
        elif re.search(rf"'{re.escape(t)}' does not depend on any axioms", out):
            axioms[t] = []
    return {"ok": r.returncode == 0 and not errors, "errors": errors, "axioms": axioms,
            "uses_sorry": [t for t, ax in axioms.items() if "sorryAx" in ax],
            "output_tail": tail(out, 40)}

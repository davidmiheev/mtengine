"""Lean 4 / Mathlib adapter: compile a source file inside the project and report axioms."""
from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

from ..core import EngineError, run_process, tail

# The Lake project (with Mathlib) that Lean sources are compiled in, first found of:
#   1. $MTENGINE_LEAN_PROJECT;
#   2. ../formal next to this checkout (where it is when mtengine is matroid_toric's engine/);
#   3. the engine's own project, created by `mte lean-init` in $XDG_DATA_HOME/mtengine/lean.
DATA_PROJECT = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "mtengine" / "lean"
SIBLING_PROJECT = Path(__file__).resolve().parents[4] / "formal"
# Mathlib release that `mte lean-init` pins by default (the toolchain comes from Mathlib's tag).
DEFAULT_MATHLIB = "v4.36.0-rc1"


def project() -> Path | None:
    env = os.environ.get("MTENGINE_LEAN_PROJECT")
    if env:
        return Path(env).expanduser().resolve()
    for p in (SIBLING_PROJECT, DATA_PROJECT):
        if (p / "lean-toolchain").exists():
            return p
    return None


def version() -> str:
    PROJECT = project()
    if PROJECT is None or not (PROJECT / "lean-toolchain").exists():
        return ("MISSING (no Lean project: run `mte lean-init`, or set MTENGINE_LEAN_PROJECT "
                "to a Lake project with Mathlib)")
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
    PROJECT = project()
    if PROJECT is None:
        raise EngineError("no Lean project: run `mte lean-init`, or set MTENGINE_LEAN_PROJECT")
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


_LAKEFILE = """name = "mte_lean"
version = "0.1.0"
defaultTargets = ["MteLean"]

[[require]]
name = "mathlib"
scope = "leanprover-community"
rev = "{rev}"

[[lean_lib]]
name = "MteLean"
"""


def init(directory: str | Path | None = None, mathlib: str = DEFAULT_MATHLIB,
         fetch_cache: bool = True, timeout: float = 7200) -> dict:
    """Create a minimal Lake project depending on Mathlib (tag or commit `mathlib`), take its
    toolchain from Mathlib's `lean-toolchain`, and download the prebuilt Mathlib (`lake exe cache
    get`; about 5 GB). Idempotent. Returns the project path and the Lean version."""
    import shutil
    import urllib.request
    d = Path(directory) if directory else DATA_PROJECT
    d.mkdir(parents=True, exist_ok=True)
    if not shutil.which("lake", path=f"{Path.home() / '.elan' / 'bin'}:{os.environ.get('PATH', '')}"):
        raise EngineError("lake not found: install elan (https://github.com/leanprover/elan)")
    url = f"https://raw.githubusercontent.com/leanprover-community/mathlib4/{mathlib}/lean-toolchain"
    with urllib.request.urlopen(url, timeout=60) as resp:
        toolchain = resp.read().decode().strip()
    (d / "lean-toolchain").write_text(toolchain + "\n")
    (d / "lakefile.toml").write_text(_LAKEFILE.format(rev=mathlib))
    (d / "MteLean.lean").write_text("import Mathlib\n")
    steps = [["lake", "update"]] + ([["lake", "exe", "cache", "get"]] if fetch_cache else [])
    for cmd in steps:
        r, _ = run_process(cmd, cwd=d, timeout=timeout)
        if r.returncode != 0:
            raise EngineError(f"{' '.join(cmd)} failed in {d}:\n{tail(r.stderr or r.stdout)}")
    return {"project": str(d), "toolchain": toolchain, "mathlib": mathlib}

"""Lean 4 / Mathlib adapter: compile a source file inside a Lake project and report axioms.

Which project `lean_check` compiles in: the first *Lake project* (a directory with a
`lean-toolchain` and a lakefile) among

  1. $MTENGINE_LEAN_PROJECT: an explicit choice, e.g. matroid_toric's `formal/` for `import Formal`;
  2. ../formal next to this checkout (mtengine as matroid_toric's `engine/` submodule);
  3. the standard project in $XDG_DATA_HOME/mtengine/lean (default ~/.local/share/mtengine/lean),
     which `mte lean-init` builds from the spec pinned in this package (`lean_project/`:
     toolchain, lakefile and lake-manifest with the exact Mathlib commit), so that every
     installation compiles against the same Lean and Mathlib.

A candidate that is not a Lake project (say, MTENGINE_LEAN_PROJECT names a directory that does
not exist in this checkout) is skipped, and `status()` says why. The chosen project must also be
*ready* (Mathlib built) for `check` to run; `status()`, `version()` (`mte versions`) and the
test suite all read the same answer, and `check` raises with the command that fixes it.

Results are cached under the Lean and Mathlib versions *and* a fingerprint of the project's own
files (its toolchain, lakefile, manifest and .lean sources), so editing a proof in a project
invalidates the results that depend on it.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from pathlib import Path

from ..core import EngineError, run_process, tail

DATA_PROJECT = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "mtengine" / "lean"
SIBLING_PROJECT = Path(__file__).resolve().parents[4] / "formal"
# The standard project's spec, shipped with the engine. To move to another Mathlib release, run
# `mte lean-init --mathlib <tag> <dir>` and copy lean-toolchain, lakefile.toml and
# lake-manifest.json from <dir> into this directory.
PINNED = Path(__file__).resolve().parents[1] / "lean_project"
PINNED_FILES = ("lean-toolchain", "lakefile.toml", "lake-manifest.json", "MteLean.lean")


def _lake_problem(p: Path) -> str | None:
    """Why `p` is not a Lake project, or None if it is one."""
    if not p.is_dir():
        return "no such directory"
    if not (p / "lean-toolchain").is_file():
        return "no lean-toolchain file"
    if not ((p / "lakefile.toml").is_file() or (p / "lakefile.lean").is_file()):
        return "no lakefile.toml or lakefile.lean"
    return None


def _manifest_rev(p: Path, package: str = "mathlib") -> str | None:
    try:
        packages = json.loads((p / "lake-manifest.json").read_text()).get("packages", [])
    except (OSError, ValueError):
        return None
    return next((q.get("rev") for q in packages if q.get("name") == package), None)


def pinned() -> dict:
    """The standard project's Lean toolchain and Mathlib commit."""
    return {"toolchain": (PINNED / "lean-toolchain").read_text().strip(),
            "mathlib": _manifest_rev(PINNED)}


def candidates() -> list[tuple[str, Path]]:
    out = []
    env = os.environ.get("MTENGINE_LEAN_PROJECT")
    if env:
        out.append(("MTENGINE_LEAN_PROJECT", Path(env).expanduser().resolve()))
    out += [("sibling", SIBLING_PROJECT), ("standard", DATA_PROJECT)]
    return out


def status() -> dict:
    """Which Lake project lean_check uses and whether it can compile in it (cheap: reads files).

    project/source: the first Lake project among the candidates (see the module docstring);
    ready: Lean can run there and, if the project requires Mathlib, Mathlib is built;
    problem: why not, with the command that fixes it; skipped: candidates passed over, and why;
    pinned: the standard spec; outdated: the standard project is on another Mathlib than pinned."""
    skipped, chosen = [], None
    for source, p in candidates():
        why = _lake_problem(p)
        if why is None:
            chosen = (source, p)
            break
        if source != "standard" and not (source == "sibling" and why == "no such directory"):
            skipped.append({"source": source, "path": str(p), "reason": why})
    out = {"project": None, "source": None, "ready": False, "problem": None,
           "toolchain": None, "mathlib": None, "skipped": skipped, "pinned": pinned(),
           "outdated": False}
    if chosen is None:
        out["problem"] = ("no Lean project: run `mte lean-init` for the standard one, or set "
                          "MTENGINE_LEAN_PROJECT to a Lake project with Mathlib")
        return out
    source, p = chosen
    out.update(project=str(p), source=source,
               toolchain=(p / "lean-toolchain").read_text().strip(), mathlib=_manifest_rev(p))
    if source == "standard" and out["mathlib"] != out["pinned"]["mathlib"]:
        out["outdated"] = True
    if not _lake():
        out["problem"] = "lake not found: install elan (https://github.com/leanprover/elan)"
    elif out["mathlib"] and not _mathlib_built(p):
        fix = "mte lean-init" if source == "standard" else f"cd {p} && lake exe cache get"
        out["problem"] = f"Mathlib is not built in {p}: run `{fix}`"
    else:
        out["ready"] = True
    return out


def _lake() -> str | None:
    return shutil.which("lake", path=f"{Path.home() / '.elan' / 'bin'}:{os.environ.get('PATH', '')}")


def _mathlib_built(p: Path) -> bool:
    build = p / ".lake" / "packages" / "mathlib" / ".lake" / "build" / "lib"
    return (build / "lean" / "Mathlib.olean").is_file() or (build / "Mathlib.olean").is_file()


def project() -> Path | None:
    """The Lake project lean_check compiles in (None if there is none)."""
    p = status()["project"]
    return Path(p) if p else None


def fingerprint(p: Path | None = None) -> str | None:
    """SHA-256 of the project's own files: toolchain, lakefile, manifest and .lean sources
    (dependencies and build outputs under .lake/ excluded)."""
    p = p or project()
    if p is None:
        return None
    h = hashlib.sha256()
    files = [p / f for f in ("lean-toolchain", "lakefile.toml", "lakefile.lean", "lake-manifest.json")]
    sources = []
    for root, dirs, names in os.walk(p):
        dirs[:] = [x for x in dirs if x not in (".lake", "lake-packages", ".git")]
        sources += [Path(root) / x for x in names if x.endswith(".lean")]
    files += sorted(f for f in sources if f.name != "lakefile.lean")
    for f in files:
        if f.is_file():
            h.update(str(f.relative_to(p)).encode() + b"\0" + f.read_bytes() + b"\0")
    return h.hexdigest()


_VERSIONS: dict[tuple, str] = {}


def version() -> str:
    """Lean version and Mathlib commit of the project in use, or MISSING (why). Memoised on the
    project's path, toolchain and manifest, so it follows `mte lean-init` in a running server."""
    st = status()
    if not st["ready"]:
        return f"MISSING ({st['problem']})"
    key = (st["project"], st["toolchain"], st["mathlib"])
    if key not in _VERSIONS:
        r, _ = run_process(["lean", "--version"], cwd=st["project"], timeout=600)
        if r.returncode != 0:
            return f"UNAVAILABLE (lean --version failed: {tail(r.stderr or r.stdout, 3)})"
        line = (r.stdout.strip().splitlines() or ["unknown"])[0]
        _VERSIONS[key] = line + (f"; mathlib {st['mathlib'][:8]}" if st["mathlib"] else "")
    return _VERSIONS[key]


def check(source: str, theorems: list[str] | None = None, timeout: float = 3600) -> dict:
    """Compile `source` with `lake env lean` in the project; print the axioms of `theorems`.

    ok is True iff Lean reports no errors. A theorem relying on `sorry` shows `sorryAx`
    among its axioms and is reported in `uses_sorry`. Raises EngineError if there is no ready
    project, or if Lean itself could not run (as opposed to reporting errors in the source).
    """
    st = status()
    if not st["ready"]:
        raise EngineError(st["problem"])
    PROJECT = Path(st["project"])
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
    if r.returncode != 0 and not errors:
        raise EngineError(f"lake env lean failed in {PROJECT} (exit {r.returncode}):\n{tail(out)}")
    axioms = {}
    for t in theorems:
        m = re.search(rf"'{re.escape(t)}' depends on axioms: \[([^\]]*)\]", out)
        if m:
            axioms[t] = [a.strip() for a in m.group(1).split(",") if a.strip()]
        elif re.search(rf"'{re.escape(t)}' does not depend on any axioms", out):
            axioms[t] = []
    return {"ok": r.returncode == 0 and not errors, "errors": errors, "axioms": axioms,
            "uses_sorry": [t for t, ax in axioms.items() if "sorryAx" in ax],
            "project": {"source": st["source"], "path": st["project"], "mathlib": st["mathlib"]},
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


def init(directory: str | Path | None = None, mathlib: str | None = None,
         fetch_cache: bool = True, timeout: float = 7200) -> dict:
    """Set up a Lake project that depends on Mathlib and download the prebuilt Mathlib (`lake exe
    cache get`; about 5 GB). Idempotent.

    Without `mathlib`: the standard project, copied from the spec pinned in this package (the
    exact Mathlib commit in its lake-manifest), in `directory` or the standard location. With
    `mathlib` (a tag or commit): a project on that release instead, its toolchain taken from
    Mathlib's and its manifest made by `lake update` (this is also how to make a new pin)."""
    import urllib.request
    d = Path(directory) if directory else DATA_PROJECT
    if not _lake():
        raise EngineError("lake not found: install elan (https://github.com/leanprover/elan)")
    d.mkdir(parents=True, exist_ok=True)
    if mathlib is None:
        for f in PINNED_FILES:
            shutil.copyfile(PINNED / f, d / f)
        steps = [["lake", "exe", "cache", "get"]] if fetch_cache else [["lake", "env", "true"]]
    else:
        url = f"https://raw.githubusercontent.com/leanprover-community/mathlib4/{mathlib}/lean-toolchain"
        with urllib.request.urlopen(url, timeout=60) as resp:
            (d / "lean-toolchain").write_text(resp.read().decode().strip() + "\n")
        (d / "lakefile.toml").write_text(_LAKEFILE.format(rev=mathlib))
        (d / "MteLean.lean").write_text("import Mathlib\n")
        steps = [["lake", "update"]] + ([["lake", "exe", "cache", "get"]] if fetch_cache else [])
    for cmd in steps:
        r, _ = run_process(cmd, cwd=d, timeout=timeout)
        if r.returncode != 0:
            raise EngineError(f"{' '.join(cmd)} failed in {d}:\n{tail(r.stderr or r.stdout)}")
    return {"project": str(d), "toolchain": (d / "lean-toolchain").read_text().strip(),
            "mathlib": _manifest_rev(d), "standard": mathlib is None}

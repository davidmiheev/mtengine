"""Regina adapter: 3- and 4-manifold triangulations, census lookup, SnapPea hyperbolic
structures, Turaev-Viro invariants, normal surfaces and knot invariants.

Regina's Python module is built for the distribution's system Python (e.g. 3.12 on Ubuntu
24.04) and does not import in an arbitrary venv, so, like every other backend, it runs in a
separate process: `regina-python` (shipped with Regina) executes a driver script that reads
a JSON request and prints a JSON reply. Set MTENGINE_REGINA_PYTHON to use another command
(e.g. a python3 that can `import regina`).

Known pitfalls absorbed here:
  * SnapPea's treatment of a *closed* triangulation is randomised (it converts it into a
    filling of a cusped manifold it builds itself) and often ends in a degenerate solution
    with a wrong volume. `hyperbolic` reconstructs it up to `attempts` times and keeps the
    first non-degenerate solution; non-degenerate solutions had the correct volume in all
    of the 60,360 attempts tested on the Hodgson-Weeks census (regina_experiments, E06).
  * Repeated fill() calls on one SnapPea object are path-dependent (each solve starts from
    the previous solution), so every request uses a fresh SnapPea triangulation.
  * turaevViroApprox(r, w) with even w equals turaevViro(r, False).evaluate(w / 2), not
    evaluate(w) as Regina's documentation says; `turaev_viro` evaluates accordingly.
"""
from __future__ import annotations

import json
import os
import shutil

from ..core import EngineError, run_process, tail


def command() -> list[str]:
    """The command that runs a Python script with `regina` importable."""
    cmd = os.environ.get("MTENGINE_REGINA_PYTHON", "regina-python")
    if not shutil.which(cmd.split()[0]):
        raise EngineError(f"{cmd!r} not found; install Regina (https://regina-normal.github.io) "
                          "or set MTENGINE_REGINA_PYTHON")
    return cmd.split()


_DRIVER = r'''
import json, math, sys
import regina

def tri(sig, dim):
    cls = {3: regina.Triangulation3, 4: regina.Triangulation4}.get(dim)
    if cls is None:
        raise ValueError(f"dimension {dim} not supported (use 3 or 4)")
    t = cls.fromIsoSig(sig)
    if t is None or t.isEmpty():
        raise ValueError(f"not a valid {dim}-dimensional isomorphism signature: {sig!r}")
    return t

def group(g):
    return {"generators": g.countGenerators(),
            "relations": [str(g.relation(i)) for i in range(g.countRelations())],
            "recognised": g.recogniseGroup() or None}

def lookup(sig):
    return [{"name": h.name(), "database": h.db().desc()} for h in regina.Census.lookup(sig)]

def invariants(sig, dim=3, recognise=False):
    t = tri(sig, dim)
    out = {"dimension": dim, "size": t.size(), "valid": t.isValid(), "closed": t.isClosed(),
           "orientable": t.isOrientable(), "ideal": t.isIdeal(), "connected": t.isConnected(),
           "vertices": t.countVertices(), "boundary_components": t.countBoundaryComponents(),
           "isosig": t.isoSig()}
    if not t.isValid():
        return out
    if dim == 3:
        out["euler_char"] = t.eulerCharManifold()
        out["homology"] = {"H1": str(t.homology(1)), "H2": str(t.homology(2))}
        out["fundamental_group"] = group(t.fundamentalGroup())
        out["census"] = lookup(t.isoSig())
        if recognise:
            r = {"irreducible": None, "sphere": None, "ball": None, "solid_torus": None}
            if t.isClosed():
                r["sphere"] = t.isSphere()
                if t.isOrientable() and t.isConnected():
                    s = t.summands()
                    r["prime_summands"] = [{"isosig": x.isoSig(), "census": lookup(x.isoSig())}
                                           for x in s]
                    r["irreducible"] = t.isIrreducible()
            elif t.hasBoundaryTriangles() and not t.isIdeal():
                r["ball"] = t.isBall()
                r["solid_torus"] = t.isSolidTorus()
            out["recognition"] = r
    else:
        out["euler_char"] = t.eulerCharManifold()
        out["homology"] = {"H1": str(t.homology(1)), "H2": str(t.homology(2))}
        out["fundamental_group"] = group(t.fundamentalGroup())
        if t.isClosed() and t.isOrientable() and t.isConnected():
            f = t.intersectionForm()
            m = f.matrix()
            out["intersection_form"] = {"rank": f.rank(), "signature": f.signature(),
                                        "even": f.even(),
                                        "matrix": [[int(str(m.entry(i, j)))
                                                    for j in range(m.columns())]
                                                   for i in range(m.rows())]}
    return out

def census_lookup(sig):
    return lookup(regina.Triangulation3.fromIsoSig(sig).isoSig())

def hyperbolic(sig, fillings=None, attempts=20):
    t = tri(sig, 3)
    tries, best = 0, None
    for tries in range(1, max(1, attempts) + 1):
        s = regina.SnapPeaTriangulation(t)
        if s.isNull():
            return {"solution": "null", "attempts": tries,
                    "note": "SnapPea could not use this triangulation"}
        for i, f in enumerate(fillings or []):
            if f is not None and not s.fill(int(f[0]), int(f[1]), i):
                raise ValueError(f"SnapPea rejected filling {f} on cusp {i}")
        sol = s.solutionType().name
        if best is None or sol in ("Geometric", "Nongeometric"):
            vol, digits = s.volumeWithPrecision()
            best = {"solution": sol, "volume": vol, "precision_digits": digits,
                    "cusps": s.countCusps(), "filled_cusps": s.countFilledCusps()}
            try:
                best["min_imaginary_shape"] = s.minImaginaryShape()
            except Exception:
                pass
            if s.countCompleteCusps() == 0 or fillings:
                best["homology_filled"] = str(s.homologyFilled())
        # Only a closed input is randomised; anything else is deterministic.
        if sol in ("Geometric", "Nongeometric") or not t.isClosed():
            break
    best["attempts"] = tries
    best["volume_trustworthy"] = best["solution"] in ("Geometric", "Nongeometric")
    return best

def turaev_viro(sig, r):
    t = tri(sig, 3)
    if not t.isClosed():
        raise ValueError("Turaev-Viro invariants need a closed triangulation")
    out = {"r": r, "exact": {}, "by_root": {}}
    for parity in ((True, False) if r % 2 else (True,)):
        v = t.turaevViro(r, parity)
        out["exact"]["odd_w" if parity else "even_w"] = str(v)
        for w in range(1, r):
            if math.gcd(w, r) == 1 and w % 2 == (1 if parity else 0):
                z = v.evaluate(w if parity else w // 2)
                out["by_root"][str(w)] = round(z.real, 12)
    return out

_LINK = {"pd": regina.Link.fromPD, "dt": regina.Link.fromDT, "gauss": regina.Link.fromGauss,
         "signed_gauss": regina.Link.fromSignedGauss,
         "oriented_gauss": regina.Link.fromOrientedGauss, "jenkins": regina.Link.fromJenkins,
         "sig": regina.Link.fromSig}

def link_invariants(code, fmt="pd", complement=True):
    if fmt not in _LINK:
        raise ValueError(f"unknown link format {fmt!r}; use one of {sorted(_LINK)}")
    k = _LINK[fmt](code)   # Regina accepts both a string and a Python sequence
    out = {"crossings": k.size(), "components": k.countComponents(),
           "classical": k.isClassical(), "writhe": k.writhe(), "sig": k.sig(),
           "jones": str(k.jones()), "homfly_lm": str(k.homflyLM()),
           "homfly_az": str(k.homflyAZ())}
    if k.isClassical():
        out["alternating"] = k.isAlternating()
        out["pd"] = k.pd()
        if k.countComponents() == 1:
            out["alexander"] = str(k.alexander())
        if complement:
            c = k.complement()
            c.simplify()
            out["complement"] = {"isosig": c.isoSig(), "size": c.size(),
                                 "census": lookup(c.isoSig())}
    return out

def normal_surfaces(sig, coords="quad", which="vertex", limit=200):
    t = tri(sig, 3)
    C = {"quad": regina.NormalCoords.Quad, "standard": regina.NormalCoords.Standard,
         "quad_oct": regina.NormalCoords.QuadOct,
         "almost_normal": regina.NormalCoords.AlmostNormal}
    W = {"vertex": regina.NormalList.Vertex, "fundamental": regina.NormalList.Fundamental}
    if coords not in C or which not in W:
        raise ValueError(f"coords in {sorted(C)}, which in {sorted(W)}")
    s = regina.NormalSurfaces(t, C[coords], W[which])
    rows = []
    for i in range(min(s.size(), limit)):
        x = s.surface(i)
        # Non-compact (spun-normal) surfaces occur in ideal triangulations; Euler
        # characteristic and the rest are only defined for compact ones.
        row = {"compact": x.isCompact(), "vertex_link": x.isVertexLinking()}
        if x.isCompact():
            row.update(euler_char=int(str(x.eulerChar())), connected=x.isConnected(),
                       orientable=x.isOrientable(), two_sided=x.isTwoSided(),
                       boundaries=x.countBoundaries())
        rows.append(row)
    return {"count": s.size(), "coords": coords, "which": which,
            "surfaces": rows, "truncated": s.size() > limit}

OPS = {"invariants": invariants, "census_lookup": census_lookup, "hyperbolic": hyperbolic,
       "turaev_viro": turaev_viro, "link_invariants": link_invariants,
       "normal_surfaces": normal_surfaces}

req = json.load(open(sys.argv[1]))
try:
    print("MTE-JSON " + json.dumps({"ok": OPS[req["op"]](**req["args"])}))
except Exception as e:
    print("MTE-JSON " + json.dumps({"error": f"{type(e).__name__}: {e}"}))
'''


def _call(op: str, args: dict, timeout: float) -> object:
    r, _ = run_process(command() + ["{dir}/driver.py", "{dir}/request.json"],
                       files={"driver.py": _DRIVER, "request.json": json.dumps({"op": op, "args": args})},
                       timeout=timeout)
    line = next((l for l in reversed(r.stdout.splitlines()) if l.startswith("MTE-JSON ")), None)
    if r.returncode != 0 or line is None:
        raise EngineError(f"regina failed (exit {r.returncode}):\n{tail(r.stderr or r.stdout)}")
    reply = json.loads(line[len("MTE-JSON "):])
    if "error" in reply:
        raise EngineError(f"regina: {reply['error']}")
    return reply["ok"]


def version() -> str:
    """Regina's version string, e.g. "Regina 7.4.1 (Upstream Ubuntu 24.04 package)"."""
    if shutil.which("regina-engine-config"):
        r, _ = run_process(["regina-engine-config", "--version"], timeout=120)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip().splitlines()[0]
    try:
        r, _ = run_process(command() + ["{dir}/v.py"],
                           files={"v.py": "import regina; print('Regina ' + regina.versionString())"},
                           timeout=120)
        return r.stdout.strip() or "unknown"
    except EngineError:
        return "MISSING"


def run(code: str, timeout: float = 600) -> str:
    """Run Python code with `regina` imported; return its standard output."""
    r, _ = run_process(command() + ["{dir}/script.py"], files={"script.py": code}, timeout=timeout)
    if r.returncode != 0:
        raise EngineError(f"regina-python failed (exit {r.returncode}):\n{tail(r.stderr or r.stdout)}")
    return r.stdout


def invariants(isosig: str, dim: int = 3, recognise: bool = False, timeout: float = 600) -> dict:
    return _call("invariants", {"sig": isosig, "dim": dim, "recognise": recognise}, timeout)


def census_lookup(isosig: str, timeout: float = 120) -> list:
    return _call("census_lookup", {"sig": isosig}, timeout)


def hyperbolic(isosig: str, fillings: list | None = None, attempts: int = 20,
               timeout: float = 600) -> dict:
    return _call("hyperbolic", {"sig": isosig, "fillings": fillings, "attempts": attempts},
                 timeout)


def turaev_viro(isosig: str, r: int, timeout: float = 3600) -> dict:
    return _call("turaev_viro", {"sig": isosig, "r": r}, timeout)


def link_invariants(code, fmt: str = "pd", complement: bool = True, timeout: float = 600) -> dict:
    return _call("link_invariants", {"code": code, "fmt": fmt, "complement": complement}, timeout)


def normal_surfaces(isosig: str, coords: str = "quad", which: str = "vertex", limit: int = 200,
                    timeout: float = 3600) -> dict:
    return _call("normal_surfaces", {"sig": isosig, "coords": coords, "which": which,
                                     "limit": limit}, timeout)

"""Public API. Every function returns JSON-serialisable data; computations return
{"value", "provenance", "cached"} from the result cache. The CLI (`mte`) and the MCP server
(`mtengine-mcp`) expose exactly the functions listed in FUNCTIONS."""
from __future__ import annotations

from typing import Any

from . import core
from .backends import gfan, lean, macaulay2, nauty, polymake, regina, singular
from .domain import hessenberg as hs
from .domain import posets

Json = dict[str, Any]


def versions() -> Json:
    """Versions of all backends ("MISSING" if a tool is not installed)."""
    return {t: core.tool_version(t) for t in
            ["engine", "python", "macaulay2", "gfan", "polymake", "singular", "nauty", "lean",
             "regina"]}


# ------------------------------------------------------------------ raw backends
def m2_run(code: str, timeout: float = 600, use_cache: bool = True) -> Json:
    """Run a Macaulay2 script and return its standard output."""
    return core.cached("macaulay2", "run", {"code": code},
                       lambda: macaulay2.run(code, timeout), use_cache)


def singular_run(code: str, timeout: float = 600, use_cache: bool = True) -> Json:
    """Run Singular code and return its standard output."""
    return core.cached("singular", "run", {"code": code},
                       lambda: singular.run(code, timeout), use_cache)


def gkm_betti(n_vars: int, n_vertices: int, edges: list[list[Any]], timeout: float = 1800,
              use_cache: bool = True) -> Json:
    """Betti numbers of a GKM manifold from its GKM graph, via Macaulay2.

    edges: [[i, j, [w_1..w_n]], ...] with vertices 0..n_vertices-1 and integer weight vectors
    (the label alpha_ij = sum w_k t_k)."""
    E = [(int(a), int(b), [int(x) for x in w]) for a, b, w in edges]
    return core.cached("macaulay2", "gkm_betti", {"n": n_vars, "v": n_vertices, "e": E},
                       lambda: macaulay2.gkm_betti(n_vars, n_vertices, E, timeout), use_cache)


def tropical_variety(variables: list[str], generators: list[str], timeout: float = 3600,
                     use_cache: bool = True) -> Json:
    """Dimension, lineality and f-vector of the tropical variety of a homogeneous prime ideal
    (gfan). Generators are polynomial strings in the given variables, e.g. "p3*p12-p2*p13+p1*p23"."""
    return core.cached("gfan", "tropical_variety", {"vars": variables, "gens": generators},
                       lambda: gfan.tropical_variety(variables, generators, timeout), use_cache)


def simplicial_homology(facets: list[list[int]], timeout: float = 3600, use_cache: bool = True) -> Json:
    """Reduced integral homology (Betti numbers and torsion) of a simplicial complex given by
    its facets (polymake/topaz)."""
    F = sorted(sorted(int(x) for x in f) for f in facets)
    return core.cached("polymake", "homology", {"facets": F},
                       lambda: polymake.homology(F, timeout), use_cache)


def graph_canonical_form(n: int, edges: list[list[int]], cells: list[list[int]] | None = None,
                         use_cache: bool = True) -> Json:
    """Canonical form of a vertex-coloured graph (nauty). Equal forms <=> isomorphic."""
    E = sorted(tuple(sorted((int(a), int(b)))) for a, b in edges)
    return core.cached("nauty", "canonical_form", {"n": n, "e": E, "cells": cells},
                       lambda: nauty.canonical_form(n, E, cells), use_cache)


def lean_check(source: str, theorems: list[str] | None = None, timeout: float = 3600,
               use_cache: bool = True) -> Json:
    """Compile Lean 4 source against the project's Mathlib; report errors and the axioms each
    named theorem depends on (sorryAx => it uses sorry)."""
    return core.cached("lean", "check", {"source": source, "theorems": theorems or []},
                       lambda: lean.check(source, theorems, timeout), use_cache)


# ------------------------------------------------------------------ Regina (low-dimensional topology)
# Triangulations are passed as Regina isomorphism signatures (e.g. "cPcbbbiht" is the
# figure-eight knot complement); get one from Regina with `tri.isoSig()`.
def regina_run(code: str, timeout: float = 600, use_cache: bool = True) -> Json:
    """Run Python code with Regina's `regina` module imported; return its standard output."""
    return core.cached("regina", "run", {"code": code},
                       lambda: regina.run(code, timeout), use_cache)


def triangulation_invariants(isosig: str, dim: int = 3, recognise: bool = False,
                             timeout: float = 600, use_cache: bool = True) -> Json:
    """Basic invariants of a 3- or 4-manifold triangulation given by its isomorphism signature:
    validity, closed/orientable/ideal, Euler characteristic, H1 and H2, a simplified pi1
    presentation (and Regina's name for the group, if recognised), census names (dim 3), and the
    intersection form (closed orientable dim 4). recognise=True (dim 3) also runs 3-sphere / ball /
    solid-torus recognition and the prime decomposition, which can be slow."""
    return core.cached("regina", "invariants", {"sig": isosig, "dim": dim, "recognise": recognise},
                       lambda: regina.invariants(isosig, dim, recognise, timeout), use_cache)


def census_lookup(isosig: str, use_cache: bool = True) -> Json:
    """Names of a 3-manifold triangulation in Regina's census databases (closed orientable and
    non-orientable, cusped hyperbolic, Hodgson-Weeks closed hyperbolic, knot/link complements).
    Only exact triangulations are found: simplify first if needed."""
    return core.cached("regina", "census_lookup", {"sig": isosig},
                       lambda: regina.census_lookup(isosig), use_cache)


def hyperbolic_structure(isosig: str, fillings: list[list[int] | None] | None = None,
                         attempts: int = 20, use_cache: bool = True) -> Json:
    """SnapPea (inside Regina): solution type, hyperbolic volume and its precision, cusps, for a
    3-manifold triangulation, optionally Dehn filled ([[p, q] or null per cusp]).
    volume_trustworthy is False for degenerate/flat solutions. Closed triangulations are retried
    up to `attempts` times because SnapPea's handling of them is random.
    Slopes are in the peripheral basis SnapPea assigns to *this* triangulation: a manifold
    with the same census name in SnapPy may be its mirror image, which turns (p, q) into
    (-p, q)."""
    return core.cached("regina", "hyperbolic",
                       {"sig": isosig, "fillings": fillings, "attempts": attempts},
                       lambda: regina.hyperbolic(isosig, fillings, attempts), use_cache)


def turaev_viro(isosig: str, r: int, timeout: float = 3600, use_cache: bool = True) -> Json:
    """Exact Turaev-Viro invariant TV_r of a closed 3-manifold triangulation, as cyclotomic field
    elements (both parities of the root of unity for odd r), and its real value at every root
    q0 = exp(i pi w / r), w coprime to r, 0 < w < r. Cost grows quickly with r and treewidth."""
    return core.cached("regina", "turaev_viro", {"sig": isosig, "r": r},
                       lambda: regina.turaev_viro(isosig, r, timeout), use_cache)


def link_invariants(code: str | list[Any], format: str = "pd", complement: bool = True,
                    use_cache: bool = True) -> Json:
    """Knot/link invariants from a diagram: crossings, components, writhe, Jones (in x = sqrt(t)),
    HOMFLY-PT (LM and AZ conventions), Alexander (knots), and the complement's simplified
    triangulation with its census names. format: pd, dt, gauss, signed_gauss, oriented_gauss,
    jenkins or sig (Regina's knot signature); codes may be strings or lists."""
    return core.cached("regina", "link_invariants",
                       {"code": code, "format": format, "complement": complement},
                       lambda: regina.link_invariants(code, format, complement), use_cache)


def pachner_walk(isosig: str, moves: int, seeds: list[int], mix44: int = 0,
                 timeout: float = 3600, use_cache: bool = True) -> Json:
    """Scramble a 3-manifold triangulation reproducibly: for each seed, `moves` random 2-3
    Pachner moves (each adds a tetrahedron), each followed by `mix44` random 4-4 moves. Returns
    [{"seed", "isosig", "size"}]. Same manifold, larger and messier triangulation. Where no 2-3
    move exists (one-tetrahedron triangulations) a 1-4 move is used, adding three tetrahedra."""
    return core.cached("regina", "pachner_walk",
                       {"sig": isosig, "moves": moves, "seeds": seeds, "mix44": mix44},
                       lambda: regina.pachner_walk(isosig, moves, seeds, mix44, timeout), use_cache)


def simplify_triangulations(isosigs: list[str], trials: int = 1, max_height: int = 0,
                            target_size: int | None = None, threads: int = 1,
                            lookup: bool = False, timeout: float = 3600,
                            use_cache: bool = True) -> Json:
    """Simplify a batch of 3-manifold triangulations with Regina. Greedy simplify() is
    randomised, so it runs `trials` independent times and keeps the smallest result; then
    simplifyExhaustive at heights 1..max_height (height h may pass through h extra tetrahedra;
    cost grows very fast with h and size) until no further reduction or `target_size` is
    reached. Per input: greedy sizes, sizes after each height, final isosig (and census names
    if lookup)."""
    return core.cached("regina", "simplify_many",
                       {"sigs": isosigs, "trials": trials, "max_height": max_height,
                        "target_size": target_size, "threads": threads, "lookup": lookup},
                       lambda: regina.simplify_many(isosigs, trials, max_height, target_size,
                                                    threads, lookup, timeout), use_cache)


def normal_surfaces(isosig: str, coords: str = "quad", which: str = "vertex", limit: int = 200,
                    timeout: float = 3600, use_cache: bool = True) -> Json:
    """Enumerate embedded normal surfaces of a 3-manifold triangulation (Regina): the number of
    vertex or fundamental surfaces in quad / standard / quad_oct / almost_normal coordinates, and
    for each (up to `limit`) Euler characteristic, orientability, two-sidedness, boundary count."""
    return core.cached("regina", "normal_surfaces",
                       {"sig": isosig, "coords": coords, "which": which, "limit": limit},
                       lambda: regina.normal_surfaces(isosig, coords, which, limit, timeout),
                       use_cache)


# ------------------------------------------------------------------ Hessenberg varieties
def hessenberg_betti(kbar: list[int], h: list[int], use_cache: bool = True) -> Json:
    """Betti numbers (beta_0, beta_2, ...) of the regular semisimple partial Hessenberg variety
    with block sizes kbar and Hessenberg function h on [len(kbar)] (BB decomposition).
    kbar = [1]*n gives Hess(S, h) in Fl(C^n)."""
    return core.cached("python", "hessenberg_betti", {"kbar": kbar, "h": h},
                       lambda: hs.betti(tuple(kbar), tuple(h)), use_cache)


def hessenberg_betti_gkm(kbar: list[int], h: list[int], timeout: float = 3600,
                         use_cache: bool = True) -> Json:
    """The same Betti numbers computed independently: Hilbert series of the GKM ring
    (Macaulay2). Agreement with hessenberg_betti is a check on both."""
    n, nv, E = hs.gkm_graph(tuple(kbar), tuple(h))
    return gkm_betti(n, nv, [[a, b, w] for a, b, w in E], timeout, use_cache)


def hessenberg_faces(kbar: list[int], h: list[int], use_cache: bool = True) -> Json:
    """Face poset of the torus action: number of faces by rank and the cover invariant
    (per rank, multiset of (lower covers, upper covers))."""
    return core.cached("python", "hessenberg_faces", {"kbar": kbar, "h": h},
                       lambda: {"by_rank": hs.faces_by_rank(tuple(kbar), tuple(h)),
                                "cover_invariant": hs.cover_invariant(tuple(kbar), tuple(h)),
                                "dimension": hs.dimension(tuple(kbar), tuple(h))}, use_cache)


def _face_poset(kbar, h):
    F = hs.faces(tuple(kbar), tuple(h)); n = sum(kbar)
    ranks = [hs.face_rank(f, n) for f in F]
    hasse = posets.hasse_edges(F, lambda f: hs.face_rank(f, n), hs.face_leq)
    return F, ranks, hasse


def hessenberg_face_poset_canonical(kbar: list[int], h: list[int], use_cache: bool = True) -> Json:
    """nauty canonical form of the face poset (Hasse diagram coloured by rank). Two such posets
    are isomorphic iff the forms are equal; use this to confirm candidates found by invariants."""
    def compute():
        F, ranks, hasse = _face_poset(kbar, h)
        return nauty.canonical_form(len(F), hasse, posets.rank_cells(ranks))
    return core.cached("nauty", "hessenberg_face_poset_canonical", {"kbar": kbar, "h": h},
                       compute, use_cache)


def hessenberg_face_poset_homology(kbar: list[int], h: list[int], drop_top: bool = True,
                                   use_cache: bool = True) -> Json:
    """Integral homology of the order complex of the face poset (minus its top if drop_top)."""
    def compute():
        F, ranks, hasse = _face_poset(kbar, h)
        top = max(ranks)
        keep = [i for i, r in enumerate(ranks) if not (drop_top and r == top)]
        re_ = {i: k for k, i in enumerate(keep)}
        facets = posets.order_complex_facets(
            len(keep), [ranks[i] for i in keep],
            [(re_[a], re_[b]) for a, b in hasse if a in re_ and b in re_])
        return polymake.homology(facets)
    return core.cached("polymake", "hessenberg_face_poset_homology",
                       {"kbar": kbar, "h": h, "drop_top": drop_top}, compute, use_cache)


# ------------------------------------------------------------------ jobs
def job_submit(function: str, arguments: dict[str, Any] | None = None) -> Json:
    """Start a long computation in the background; returns a job id for job_status."""
    if function not in FUNCTIONS or function.startswith("job_"):
        raise core.EngineError(f"unknown function {function}")
    return {"job_id": core.submit(FUNCTIONS[function], **(arguments or {}))}


def job_status(job_id: str) -> Json:
    """State of a background job (queued/running/done/error) and its result when done."""
    return core.job_status(job_id)


FUNCTIONS = {f.__name__: f for f in [
    versions, m2_run, singular_run, gkm_betti, tropical_variety, simplicial_homology,
    graph_canonical_form, lean_check, regina_run, triangulation_invariants, census_lookup,
    hyperbolic_structure, turaev_viro, link_invariants, normal_surfaces, pachner_walk,
    simplify_triangulations, hessenberg_betti,
    hessenberg_betti_gkm, hessenberg_faces, hessenberg_face_poset_canonical,
    hessenberg_face_poset_homology, job_submit, job_status]}

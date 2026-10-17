"""Public API. Every function returns JSON-serialisable data; computations return
{"value", "provenance", "cached"} from the result cache. The CLI (`mte`) and the MCP server
(`mtengine-mcp`) expose exactly the functions listed in FUNCTIONS."""
from __future__ import annotations

from typing import Any

from . import core
from .backends import gfan, lean, macaulay2, nauty, polymake, singular
from .domain import hessenberg as hs
from .domain import posets

Json = dict[str, Any]


def versions() -> Json:
    """Versions of all backends ("MISSING" if a tool is not installed)."""
    return {t: core.tool_version(t) for t in
            ["engine", "python", "macaulay2", "gfan", "polymake", "singular", "nauty", "lean"]}


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
    graph_canonical_form, lean_check, hessenberg_betti, hessenberg_betti_gkm, hessenberg_faces,
    hessenberg_face_poset_canonical, hessenberg_face_poset_homology, job_submit, job_status]}

"""Macaulay2 adapter."""
from __future__ import annotations

import re

from ..core import EngineError, run_process, tail


def run(code: str, timeout: float = 600) -> str:
    """Run a Macaulay2 script; return its standard output."""
    r, _ = run_process(["M2", "--script", "prog.m2"], files={"prog.m2": code}, timeout=timeout)
    if r.returncode != 0:
        raise EngineError(f"Macaulay2 failed (exit {r.returncode}):\n{tail(r.stderr or r.stdout)}")
    return r.stdout


def _linear_form(weight: list[int]) -> str:
    terms = [f"({c})*R_{i}" for i, c in enumerate(weight) if c]
    if not terms:
        raise EngineError("GKM edge with zero weight")
    return "+".join(terms)


def gkm_betti(n_vars: int, n_vertices: int, edges: list[tuple[int, int, list[int]]],
              timeout: float = 1800) -> dict:
    """Betti numbers of a GKM graph from the Hilbert series of its ring of graph functions.

    The ring is the kernel of  (+)_v R -> (+)_edges R/(alpha_e),  (f_v) |-> (f_p - f_q),
    R = Q[t_1..t_n] with deg t_i = 1 (so T stands for cohomological degree 2). For an
    equivariantly formal GKM manifold, Hilb = (sum_k beta_2k T^k) / (1-T)^n.
    """
    if not edges:
        raise EngineError("GKM graph without edges")
    rows = ",".join(f"({a},{b})" for a, b, _ in edges)
    wts = ",".join(_linear_form(w) for _, _, w in edges)
    code = f"""
R = QQ[t_1..t_{n_vars}];
N = {n_vertices};
rows = {{{rows}}};
wts = {{{wts}}};
Tgt = directSum apply(wts, al -> coker matrix {{{{al}}}});
M = matrix apply(#rows, e -> (r := rows#e; apply(N, c -> if c == r#0 then 1_R else if c == r#1 then -1_R else 0_R)));
K = kernel map(Tgt, R^N, M);
hs = reduceHilbert hilbertSeries K;
num = numerator hs;
T = (ring num)_0;
print("BETTI " | toString apply(first degree num + 1, k -> coefficient(T^k, num)));
print("DENOM " | toString denominator hs);
"""
    out = run(code, timeout)
    betti = re.search(r"BETTI \{([^}]*)\}", out)
    denom = re.search(r"DENOM (.*)", out)
    if not betti:
        raise EngineError(f"could not parse Macaulay2 output:\n{tail(out)}")
    return {"betti": [int(x) for x in betti.group(1).split(",")],
            "denominator": denom.group(1).strip() if denom else None}

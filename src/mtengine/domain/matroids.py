"""Linear matroids, oriented matroids and hyperplane arrangements, in exact rational arithmetic.

A matroid is given by a family of vectors (the columns of a matrix) with integer or rational
entries ("3", "-1/2"). Everything is computed from the lattice of flats, which is enumerated by
closure (polynomially many steps per flat), so it scales with the number of flats rather than
with 2^n. Only the Tutte polynomial and the chirotope enumerate subsets, and they are capped.

Conventions: rank function r, ground set E = {0..n-1}; characteristic polynomial
chi(t) = sum_F mu(bottom, F) t^(r(E) - r(F)) over flats F (0 if there is a loop); Poincare
polynomial pi(t) = sum_F |mu(bottom, F)| t^r(F) = (-t)^r chi(-1/t), the Hilbert series of the
Orlik-Solomon algebra and the Poincare polynomial of the complement of the complexified
arrangement; beta invariant beta = (-1)^(r-1) chi'(1).
"""
from __future__ import annotations

from fractions import Fraction
from itertools import combinations
from math import comb
from typing import Any, Sequence

from ..core import EngineError

Vec = tuple[Fraction, ...]


# ------------------------------------------------------------------ exact linear algebra
def parse_vectors(vectors: Sequence[Sequence[Any]]) -> list[Vec]:
    """Columns as exact rationals; all of the same length."""
    if not vectors:
        raise EngineError("need at least one vector")
    try:
        V = [tuple(Fraction(str(x)) for x in v) for v in vectors]
    except (ValueError, ZeroDivisionError) as e:
        raise EngineError(f"vector entries must be integers or rationals like '1/2': {e}") from e
    d = len(V[0])
    if d == 0 or any(len(v) != d for v in V):
        raise EngineError("all vectors must have the same positive length")
    return V


class _Echelon:
    """Incremental row-echelon basis of a span: add() reports whether a vector was new."""

    def __init__(self) -> None:
        self.rows: list[tuple[int, list[Fraction]]] = []   # (pivot index, row with 1 at pivot)

    def reduce(self, v: Sequence[Fraction]) -> list[Fraction]:
        w = list(v)
        for p, row in self.rows:
            c = w[p]
            if c:
                w = [a - c * b for a, b in zip(w, row)]
        return w

    def add(self, v: Sequence[Fraction]) -> bool:
        w = self.reduce(v)
        for i, c in enumerate(w):
            if c:
                self.rows.append((i, [x / c for x in w]))
                return True
        return False

    def copy(self) -> "_Echelon":
        e = _Echelon()
        e.rows = list(self.rows)
        return e


def rank_of(V: Sequence[Vec], X) -> int:
    e = _Echelon()
    return sum(e.add(V[i]) for i in X)


def closure(V: Sequence[Vec], X) -> frozenset[int]:
    e = _Echelon()
    for i in X:
        e.add(V[i])
    return frozenset(j for j in range(len(V)) if not any(e.reduce(V[j])))


# ------------------------------------------------------------------ lattice of flats
def flats_by_rank(V: Sequence[Vec]) -> list[list[frozenset[int]]]:
    """All flats, grouped by rank: rank k+1 flats are closures of F + e over rank-k flats F."""
    n = len(V)
    levels = [[closure(V, ())]]
    while True:
        nxt: set[frozenset[int]] = set()
        for F in levels[-1]:
            done: set[int] = set(F)
            for e in range(n):
                if e not in done:
                    G = closure(V, F | {e})
                    done |= G
                    nxt.add(G)
        if not nxt:
            return levels
        levels.append(sorted(nxt, key=sorted))


def mobius_from_bottom(levels: list[list[frozenset[int]]]) -> dict[frozenset[int], int]:
    mu: dict[frozenset[int], int] = {levels[0][0]: 1}
    below: list[frozenset[int]] = [levels[0][0]]
    for level in levels[1:]:
        for F in level:
            mu[F] = -sum(mu[G] for G in below if G <= F)
        below.extend(level)
    return mu


def _poly_eval(c: list[int], x: int) -> int:
    return sum(a * x ** i for i, a in enumerate(c))


def _divide_by_t_minus_1(c: list[int]) -> list[int]:
    """Exact division of sum c_i t^i by (t - 1) (synthetic division at 1)."""
    if _poly_eval(c, 1) != 0:
        raise EngineError("internal: polynomial not divisible by t - 1")
    q = [0] * (len(c) - 1)
    acc = 0
    for i in range(len(c) - 1, 0, -1):
        acc += c[i]
        q[i - 1] = acc
    return q


def invariants(V: Sequence[Vec], tutte_max: int = 16, chirotope_max: int = 20000) -> dict:
    """Matroid invariants of the columns V (see the module docstring for conventions)."""
    n = len(V)
    levels = flats_by_rank(V)
    r = len(levels) - 1
    loops = sorted(levels[0][0])
    mu = mobius_from_bottom(levels)
    chi = [0] * (r + 1)           # chi[i] = coefficient of t^i
    pi = [0] * (r + 1)            # pi[k]  = coefficient of t^k
    if not loops:
        for k, level in enumerate(levels):
            for F in level:
                chi[r - k] += mu[F]
                pi[k] += abs(mu[F])
    dchi1 = sum(i * a for i, a in enumerate(chi))
    parallel = sorted(sorted(F) for F in (levels[1] if r >= 1 else []) if len(F) - len(loops) > 1)
    out: dict[str, Any] = {
        "n": n, "rank": r, "loops": loops,
        "parallel_classes": [sorted(set(F) - set(loops)) for F in parallel],
        "simple": not loops and not parallel,
        "flats_by_rank": [len(level) for level in levels],
        "flats": [[sorted(F) for F in level] for level in levels] if sum(map(len, levels)) <= 500 else None,
        "mobius_bottom_top": mu[levels[-1][0]] if not loops else 0,
        "characteristic_polynomial": chi,
        "poincare_polynomial": pi,
        "beta_invariant": (-1) ** (r - 1) * dchi1 if r >= 1 else 0,
        "n_bases": None, "independent_sets_by_size": None, "tutte_polynomial": None,
    }
    if n <= tutte_max:
        out.update(_subset_counts(V, r))
    return out


def _subset_counts(V: Sequence[Vec], r: int) -> dict:
    """Rank generating data over all 2^n subsets by depth-first search with incremental echelon
    forms: the Tutte polynomial T(x, y) = sum_A (x-1)^(r-r(A)) (y-1)^(|A|-r(A)) and counts of
    independent sets. Tutte coefficients are returned as {"i,j": c} for c x^i y^j."""
    n = len(V)
    by = {}   # (r(A), |A|) -> count
    def dfs(start: int, ech: _Echelon, rk: int, size: int) -> None:
        by[(rk, size)] = by.get((rk, size), 0) + 1
        for e in range(start, n):
            nxt = ech.copy()
            dfs(e + 1, nxt, rk + nxt.add(V[e]), size + 1)
    dfs(0, _Echelon(), 0, 0)
    # expand (x-1)^a (y-1)^b
    T: dict[tuple[int, int], int] = {}
    for (rk, size), c in by.items():
        a, b = r - rk, size - rk
        for i in range(a + 1):
            for j in range(b + 1):
                coef = c * comb(a, i) * comb(b, j) * (-1) ** (a - i + b - j)
                T[(i, j)] = T.get((i, j), 0) + coef
    indep = [by.get((k, k), 0) for k in range(r + 1)]
    return {"tutte_polynomial": {f"{i},{j}": c for (i, j), c in sorted(T.items()) if c},
            "independent_sets_by_size": indep, "n_bases": indep[r]}


def circuits(V: Sequence[Vec], max_size: int | None = None) -> list[list[int]]:
    """Minimal dependent sets (size <= rank + 1), by increasing size."""
    n = len(V)
    r = rank_of(V, range(n))
    out: list[frozenset[int]] = []
    for k in range(1, min(r + 1, max_size or n) + 1):
        for S in combinations(range(n), k):
            fs = frozenset(S)
            if any(C <= fs for C in out):
                continue
            if rank_of(V, S) < k:     # dependent, and no smaller circuit inside => minimal
                out.append(fs)
    return [sorted(C) for C in out]


# ------------------------------------------------------------------ oriented matroids
def _det(M: list[list[Fraction]]) -> Fraction:
    M = [row[:] for row in M]
    n, d = len(M), Fraction(1)
    for c in range(n):
        p = next((i for i in range(c, n) if M[i][c]), None)
        if p is None:
            return Fraction(0)
        if p != c:
            M[c], M[p] = M[p], M[c]
            d = -d
        d *= M[c][c]
        for i in range(c + 1, n):
            f = M[i][c] / M[c][c]
            if f:
                M[i] = [a - f * b for a, b in zip(M[i], M[c])]
    return d


def chirotope(V: Sequence[Vec], limit: int = 20000) -> dict:
    """Chirotope of a real vector configuration: the signs of the maximal minors over all
    rank-subsets in lexicographic order ('+', '-', '0'), computed in coordinates of r rows that
    span the row space. Defined up to a global sign; normalised so the first nonzero is '+'."""
    n = len(V)
    d = len(V[0])
    ech, rows = _Echelon(), []
    for i in range(d):                  # pick r linearly independent rows
        if ech.add([v[i] for v in V]):
            rows.append(i)
    r = len(rows)
    if comb(n, r) > limit:
        raise EngineError(f"chirotope has C({n},{r}) = {comb(n, r)} entries, over the limit {limit}")
    signs = []
    for B in combinations(range(n), r):
        x = _det([[V[j][i] for j in B] for i in rows]) if r else Fraction(1)
        signs.append("+" if x > 0 else "-" if x < 0 else "0")
    first = next((s for s in signs if s != "0"), "+")
    if first == "-":
        signs = [{"+": "-", "-": "+", "0": "0"}[s] for s in signs]
    return {"rank": r, "order": "lexicographic r-subsets of 0..n-1", "chirotope": "".join(signs)}


def _nullvector(V: Sequence[Vec], C: Sequence[int]) -> list[Fraction]:
    """The dependency of a circuit C: coefficients c with sum c_j V[C[j]] = 0, c[0] = 1."""
    d = len(V[0])
    k = len(C)
    # solve sum_{j>=1} c_j V[C[j]] = -V[C[0]] by elimination on the d x (k-1 | 1) system
    A = [[V[C[j]][i] for j in range(1, k)] + [-V[C[0]][i]] for i in range(d)]
    row = 0
    piv = []
    for c in range(k - 1):
        p = next((i for i in range(row, d) if A[i][c]), None)
        if p is None:
            continue
        A[row], A[p] = A[p], A[row]
        A[row] = [x / A[row][c] for x in A[row]]
        for i in range(d):
            if i != row and A[i][c]:
                f = A[i][c]
                A[i] = [a - f * b for a, b in zip(A[i], A[row])]
        piv.append(c)
        row += 1
    out = [Fraction(1)] + [Fraction(0)] * (k - 1)
    for i, c in enumerate(piv):
        out[c + 1] = A[i][-1]
    return out


def signed_circuits(V: Sequence[Vec]) -> list[dict[int, int]]:
    """Signed circuits {element: +1 or -1}, one of each opposite pair (the first element +)."""
    out = []
    for C in circuits(V):
        c = _nullvector(V, C)
        out.append({e: (1 if x > 0 else -1) for e, x in zip(C, c)})
    return out


def _chirotope_map(V: Sequence[Vec]) -> tuple[int, dict[tuple[int, ...], int]]:
    n, d = len(V), len(V[0])
    ech, rows = _Echelon(), []
    for i in range(d):
        if ech.add([v[i] for v in V]):
            rows.append(i)
    r = len(rows)
    chi = {}
    for B in combinations(range(n), r):
        x = _det([[V[j][i] for j in B] for i in rows]) if r else Fraction(1)
        chi[B] = 1 if x > 0 else -1 if x < 0 else 0
    return r, chi


def _perm_sign(seq: Sequence[int]) -> int:
    s, seq = 1, list(seq)
    for i in range(len(seq)):
        for j in range(i + 1, len(seq)):
            if seq[i] > seq[j]:
                s = -s
    return s


def oriented(V: Sequence[Vec], canon_max: int = 7) -> dict:
    """The oriented matroid of a real vector configuration.

    acyclic: the vectors lie in an open half-space (no positive circuit); totally_cyclic: every
    element lies in a positive circuit (the origin is in the relative interior of the convex
    hull). index_set: the numbers of vectors on the negative side of a generic hyperplane, over
    all generic hyperplanes (for tangent weights at a fixed point: the Morse indices the point
    can have for a generic circle). For at most canon_max elements, two canonical chirotopes:
    `oriented_class` up to relabelling (and the global sign), and `reorientation_class` up to
    relabelling and reversing the signs of any elements. Two configurations have isomorphic
    oriented matroids iff the first agree, and are reorientation equivalent iff the second do."""
    from itertools import permutations, product
    n = len(V)
    r, chi = _chirotope_map(V)
    sc = signed_circuits(V)
    positive = [C for C in sc if len(set(C.values())) == 1]
    covered = set().union(*[set(C) for C in positive]) if positive else set()
    # topes: sign vectors of generic functionals = sign vectors orthogonal to no signed circuit
    # (a sign vector is a tope iff no circuit is conformal with it up to sign)
    index_set = None
    n_topes = None
    if n <= 16 and not any(len(C) == 1 for C in sc):
        par = [C for C in sc if len(C) == 2]                 # parallel pairs force signs
        idx = set()
        cnt = 0
        for signs in product((1, -1), repeat=n):
            ok = True
            for C in sc:
                vals = {signs[e] * s for e, s in C.items()}
                if len(vals) == 1:                           # sum of positive multiples cannot vanish
                    ok = False
                    break
            if ok:
                cnt += 1
                idx.add(sum(1 for x in signs if x < 0))
        index_set, n_topes = sorted(idx), cnt
    out = {"n": n, "rank": r, "acyclic": not positive, "totally_cyclic": len(covered) == n and n > 0,
           "n_positive_circuits": len(positive), "n_topes": n_topes, "index_set": index_set,
           "oriented_class": None, "reorientation_class": None}
    if n <= canon_max:
        bases = list(combinations(range(n), r))
        sym = {1: "+", -1: "-", 0: "0"}
        best_o = best_r = None
        for perm in permutations(range(n)):
            img = []
            for B in bases:                                  # chi'(B) = chi(perm(B)), sorted
                PB = [perm[b] for b in B]
                img.append(_perm_sign(PB) * chi[tuple(sorted(PB))])
            for g in (1, -1):
                cand = tuple(g * x for x in img)
                if best_o is None or cand > best_o:
                    best_o = cand
            for eps in product((1, -1), repeat=n):
                cand = []
                for B, x in zip(bases, img):
                    for b in B:
                        x *= eps[b]
                    cand.append(x)
                cand = tuple(cand)
                if best_r is None or cand > best_r:
                    best_r = cand
        out["oriented_class"] = "".join(sym[x] for x in best_o)
        out["reorientation_class"] = "".join(sym[x] for x in best_r)
    return out


# ------------------------------------------------------------------ Kazhdan-Lusztig theory
def _padd(a: list[int], b: list[int], sign: int = 1) -> list[int]:
    out = [0] * max(len(a), len(b))
    for i, x in enumerate(a):
        out[i] += x
    for i, x in enumerate(b):
        out[i] += sign * x
    return out


def _pmul(a: list[int], b: list[int]) -> list[int]:
    if not a or not b:
        return []
    out = [0] * (len(a) + len(b) - 1)
    for i, x in enumerate(a):
        if x:
            for j, y in enumerate(b):
                out[i + j] += x * y
    return out


def _trim(a: list[int]) -> list[int]:
    a = list(a)
    while len(a) > 1 and a[-1] == 0:
        a.pop()
    return a or [0]


def kazhdan_lusztig(V: Sequence[Vec], max_flats: int = 1500) -> dict:
    """Kazhdan-Lusztig polynomial P_M(t) and Z-polynomial Z_M(t) of the linear matroid of V
    (Elias-Proudfoot-Wakefield; Proudfoot-Xu-Young), coefficient lists, lowest degree first.

    P is defined by P = 1 in rank 0, deg P < rank/2 in positive rank, and
    t^rank P_M(1/t) = sum over flats F of chi_{M|F}(t) P_{M/F}(t); it is computed for every
    upper interval of the lattice of flats. Z_M(t) = sum_F t^rank(F) P_{M/F}(t) is palindromic
    of degree rank and is the Hilbert series of the intersection cohomology module IH(M) of
    Braden-Huh-Matherne-Proudfoot-Wang (with t of degree 2). Loops are ignored and parallel
    elements identified, as both polynomials depend only on the lattice of flats."""
    levels = flats_by_rank(V)
    r = len(levels) - 1
    flats = [F for level in levels for F in level]
    if len(flats) > max_flats:
        raise EngineError(f"{len(flats)} flats, over the limit {max_flats}")
    rk = {F: k for k, level in enumerate(levels) for F in level}
    above = {F: [G for G in flats if F < G] for F in flats}
    mu: dict[tuple[frozenset[int], frozenset[int]], int] = {}
    for F in flats:                                  # mu(F, G) for G >= F, by increasing rank
        mu[F, F] = 1
        for G in above[F]:                           # `flats` is sorted by rank
            mu[F, G] = -sum(mu[F, H] for H in flats if (H == F or F < H) and H < G)
    top = levels[-1][0]

    def chi(F, G):                                   # characteristic polynomial of [F, G]
        d = rk[G] - rk[F]
        out = [0] * (d + 1)
        for H in flats:
            if (H == F or F < H) and (H == G or H < G):
                out[rk[G] - rk[H]] += mu[F, H]
        return out

    P: dict[frozenset[int], list[int]] = {}          # P of the interval [F, top]
    for F in reversed(flats):                        # decreasing rank
        d = r - rk[F]
        if d == 0:
            P[F] = [1]
            continue
        Q: list[int] = []
        for G in above[F]:
            Q = _padd(Q, _pmul(chi(F, G), P[G]))
        # t^d P(1/t) - P(t) = Q(t), deg P < d/2
        p = [-(Q[i] if i < len(Q) else 0) for i in range((d + 1) // 2)]
        for i in range(d + 1):                       # consistency of the defining recursion
            q = Q[i] if i < len(Q) else 0
            want = (p[d - i] if d - i < len(p) else 0) - (p[i] if i < len(p) else 0)
            if q != want:
                raise EngineError("Kazhdan-Lusztig recursion is inconsistent (internal error)")
        P[F] = _trim(p)
    Z: list[int] = []
    for F in flats:
        Z = _padd(Z, [0] * rk[F] + P[F])
    Z = _trim(Z) + [0] * (r + 1 - len(_trim(Z)))
    bottom = levels[0][0]
    return {"rank": r, "n_flats": len(flats), "kl_polynomial": P[bottom], "z_polynomial": Z,
            "z_palindromic": Z == Z[::-1], "ih_total_dimension": sum(Z)}


def chow_hilbert_series(V: Sequence[Vec], augmented: bool = False) -> list[int]:
    """Hilbert function of the Chow ring (or augmented Chow ring) of the linear matroid of V,
    from the Feichtner-Yuzvinsky basis: a sum over chains of flats F_1 < ... < F_k of
    prod_i (t + ... + t^(rk F_i - rk F_{i-1} - 1)), with F_0 the bottom flat; in the augmented
    case the first factor is t + ... + t^(rk F_1) instead."""
    levels = flats_by_rank(V)
    r = len(levels) - 1
    flats = [F for level in levels for F in level]
    rk = {F: k for k, level in enumerate(levels) for F in level}
    w = lambda d: [0] + [1] * max(d - 1, 0)          # t + ... + t^(d-1)
    f: dict[frozenset[int], list[int]] = {}
    total = [1]
    for F in flats:
        if rk[F] == 0:
            f[F] = [0]
            continue
        acc = w(rk[F] + 1) if augmented else w(rk[F])
        for G in flats:
            if G < F and rk[G] > 0:
                acc = _padd(acc, _pmul(f[G], w(rk[F] - rk[G])))
        f[F] = acc
        total = _padd(total, acc)
    total = _trim(total)
    return total + [0] * (r + 1 - len(total)) if augmented else total


# ------------------------------------------------------------------ hyperplane arrangements
def arrangement(normals: Sequence[Sequence[Any]], constants: Sequence[Any] | None = None) -> dict:
    """Invariants of the real arrangement {a_i . x = b_i} in R^d (central when constants is None).

    Uses the matroid of the normals (central) or of the cone (affine): chi_A(t) =
    t^(d - r) chi_M(t), and for the cone cA, chi_cA = (t - 1) chi_A. Zaslavsky: regions =
    (-1)^d chi_A(-1), bounded regions = (-1)^rank chi_A(1). The Betti numbers of the complement
    of the complexified arrangement are the coefficients of (-t)^d chi_A(-1/t)."""
    A = parse_vectors(normals)
    d = len(A[0])
    if any(not any(a) for a in A):
        raise EngineError("a normal vector is zero")
    if constants is None:
        V, central = A, True
    else:
        if len(constants) != len(A):
            raise EngineError("need one constant per hyperplane")
        b = [Fraction(str(x)) for x in constants]
        V = [(-bi,) + a for a, bi in zip(A, b)] + [(Fraction(1),) + (Fraction(0),) * d]
        central = False
    # repeated hyperplanes count once: keep one element per parallel class (no loops: the
    # normals are nonzero, and the cone's extra hyperplane is parallel to none of the others)
    reps = sorted({min(closure(V, [i])) for i in range(len(V))})
    if not central and len(V) - 1 not in reps:
        raise EngineError("internal: hyperplane at infinity merged")
    Vs = [V[i] for i in reps]
    h0 = len(Vs) - 1                                   # the cone's hyperplane x_0 = 0
    inv = invariants(Vs, tutte_max=-1)
    chi_m = inv["characteristic_polynomial"]
    levels = flats_by_rank(Vs)
    rk_normals = rank_of(A, range(len(A)))
    amb = d if central else d + 1
    chi = [0] * (amb - inv["rank"]) + chi_m             # t^(amb - r) chi_M
    if not central:
        chi = _divide_by_t_minus_1(chi)
        poset = [c for c in (sum(1 for F in level if h0 not in F) for level in levels) if c]
    else:
        poset = [len(level) for level in levels]
    while len(chi) > 1 and chi[-1] == 0:
        chi.pop()
    deg = d
    betti = [abs(chi[deg - k]) if 0 <= deg - k < len(chi) else 0 for k in range(deg + 1)]
    while len(betti) > 1 and betti[-1] == 0:
        betti.pop()
    return {
        "ambient_dim": d, "central": central, "n_hyperplanes": len(Vs) - (0 if central else 1),
        "rank": rk_normals,
        "characteristic_polynomial": chi,
        "intersection_poset_by_rank": poset,
        "regions": (-1) ** d * _poly_eval(chi, -1),
        "bounded_regions": (-1) ** rk_normals * _poly_eval(chi, 1),
        "complement_betti": betti,
    }

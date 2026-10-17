"""Regular semisimple (partial) Hessenberg varieties: fixed points, tangent weights, Betti
numbers, GKM graphs and face posets.

Data: a composition kbar = (k_1,...,k_s) of n and a Hessenberg function h on [s]; Gamma_h is
the graph on [s] with edges {a,b}, a < b <= h(a). kbar = (1,...,1) is the full-flag case.
Sources: De Mari-Procesi-Shayman (1992) for the full case; Ayzenberg-Buchstaber, IMRN 2024,
Thm 2 and its proof for fixed points, tangent weights and faces of the partial case.
Validated against known values in tests/test_hessenberg.py and against Macaulay2 GKM
computations in tests/test_backends.py.
"""
from __future__ import annotations

from collections import Counter
from itertools import combinations, product


def compositions(n: int):
    if n == 0:
        yield (); return
    for first in range(1, n + 1):
        for rest in compositions(n - first):
            yield (first,) + rest


def hessenberg_functions(s: int) -> list[tuple[int, ...]]:
    def rec(j, lo):
        if j > s:
            yield (); return
        for v in range(max(j, lo), s + 1):
            for rest in rec(j + 1, v):
                yield (v,) + rest
    return list(rec(1, 1))


def check_data(kbar, h) -> None:
    kbar, h = tuple(kbar), tuple(h)
    s = len(kbar)
    if not s or any(k < 1 for k in kbar):
        raise ValueError("kbar must be a composition (positive parts)")
    if len(h) != s or any(not (j + 1 <= h[j] <= s) for j in range(s)) or any(h[j] > h[j + 1] for j in range(s - 1)):
        raise ValueError(f"h={h} is not a Hessenberg function on [{s}]")


def graph(h) -> frozenset:
    s = len(h)
    return frozenset(frozenset((a, b)) for a in range(1, s + 1) for b in range(a + 1, h[a - 1] + 1))


def fixed_points(kbar) -> list[tuple[frozenset, ...]]:
    """Ordered set partitions (J_1..J_s) of [n] with |J_a| = k_a."""
    n = sum(kbar); out = []
    def rec(remaining, a, acc):
        if a == len(kbar):
            out.append(tuple(acc)); return
        for blk in combinations(sorted(remaining), kbar[a]):
            rec(remaining - set(blk), a + 1, acc + [frozenset(blk)])
    rec(set(range(1, n + 1)), 0, [])
    return out


def tangent_pairs(J, h):
    """(x, y) with x in J_a, y in J_b, a < b <= h(a): the tangent weights are e_x - e_y."""
    s = len(J)
    return [(x, y) for a in range(1, s + 1) for b in range(a + 1, h[a - 1] + 1)
            for x in J[a - 1] for y in J[b - 1]]


def betti(kbar, h) -> list[int]:
    """beta_0, beta_2, ...: Bialynicki-Birula count, ind(J) = #{tangent pairs (x,y) : x > y}."""
    check_data(kbar, h)
    P = Counter(sum(1 for x, y in tangent_pairs(J, h) if x > y) for J in fixed_points(kbar))
    return [P[k] for k in range(max(P) + 1)]


def dimension(kbar, h) -> int:
    return sum(kbar[a - 1] * kbar[b - 1] for a in range(1, len(kbar) + 1) for b in range(a + 1, h[a - 1] + 1))


def gkm_graph(kbar, h) -> tuple[int, int, list[tuple[int, int, list[int]]]]:
    """(n_vars, n_vertices, edges (i, j, weight)) of the GKM graph: vertices are the fixed
    points; J ~ J' when J' swaps x in J_a with y in J_b, a < b <= h(a); weight e_x - e_y."""
    check_data(kbar, h)
    n = sum(kbar); V = fixed_points(kbar); idx = {J: i for i, J in enumerate(V)}
    edges = []
    for J in V:
        for x, y in tangent_pairs(J, h):
            J2 = tuple((blk - {x}) | {y} if x in blk else (blk - {y}) | {x} if y in blk else blk for blk in J)
            i, j = idx[J], idx[J2]
            if i < j:
                w = [0] * n; w[x - 1], w[y - 1] = 1, -1
                edges.append((i, j, w))
    return n, len(V), edges


# ------------------------------------------------------------------ faces
def _connected(supp, E) -> bool:
    supp = set(supp); start = next(iter(supp)); seen = {start}; stack = [start]
    while stack:
        a = stack.pop()
        for e in E:
            if a in e:
                (b,) = e - {a}
                if b in supp and b not in seen:
                    seen.add(b); stack.append(b)
    return seen == supp


def admissible(c, E) -> bool:
    """A block with part-counts c is a connected induced subgraph of the inflated graph."""
    supp = [i + 1 for i, x in enumerate(c) if x]
    if not supp:
        return False
    if len(supp) == 1:
        return sum(c) == 1
    return _connected(supp, E)


def set_partitions(items):
    items = list(items)
    if not items:
        yield []; return
    first, rest = items[0], items[1:]
    for p in set_partitions(rest):
        for i in range(len(p)):
            yield p[:i] + [p[i] | {first}] + p[i + 1:]
        yield p + [{first}]


def _count_vectors(size, bound):
    for c in product(*(range(min(k, size) + 1) for k in bound)):
        if sum(c) == size:
            yield c


def faces(kbar, h) -> list[frozenset]:
    """Faces as frozensets of (block of coordinates, part-count vector)."""
    check_data(kbar, h)
    n = sum(kbar); E = graph(h); out = []
    for P in set_partitions(range(1, n + 1)):
        blocks = [frozenset(b) for b in P]
        options = [[c for c in _count_vectors(len(b), kbar) if admissible(c, E)] for b in blocks]
        for choice in product(*options):
            if tuple(map(sum, zip(*choice))) == tuple(kbar):
                out.append(frozenset(zip(blocks, choice)))
    return out


def face_rank(face, n) -> int:
    return n - len(face)


def face_leq(f1, f2) -> bool:
    for W, c in f2:
        parts = [(W1, c1) for W1, c1 in f1 if W1 <= W]
        if sum(len(W1) for W1, _ in parts) != len(W):
            return False
        if tuple(map(sum, zip(*[c1 for _, c1 in parts]))) != c:
            return False
    return True


def lower_covers(face, E) -> int:
    count = 0
    for W, c in face:
        Wl = sorted(W)
        for r in range(1, len(Wl)):
            for A in combinations(Wl, r):
                if Wl[0] not in A:
                    continue
                for c1 in _count_vectors(len(A), c):
                    c2 = tuple(a - b for a, b in zip(c, c1))
                    if min(c2) >= 0 and admissible(c1, E) and admissible(c2, E):
                        count += 1
    return count


def upper_covers(face, E) -> int:
    return sum(1 for (_, c1), (_, c2) in combinations(list(face), 2)
               if admissible(tuple(a + b for a, b in zip(c1, c2)), E))


def faces_by_rank(kbar, h) -> list[int]:
    n = sum(kbar); c = Counter(face_rank(f, n) for f in faces(kbar, h))
    return [c[r] for r in range(max(c) + 1)]


def cover_invariant(kbar, h) -> list:
    """Per rank, the multiset of (lower covers, upper covers): an isomorphism invariant."""
    n = sum(kbar); E = graph(h); inv: dict[int, Counter] = {}
    for f in faces(kbar, h):
        inv.setdefault(face_rank(f, n), Counter())[(lower_covers(f, E), upper_covers(f, E))] += 1
    return [sorted([list(k), v] for k, v in inv[r].items()) for r in sorted(inv)]

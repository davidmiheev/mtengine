"""Graded posets: order complexes (for polymake) and canonical forms (via nauty)."""
from __future__ import annotations

from typing import Callable, Hashable, Sequence


def hasse_edges(elements: Sequence[Hashable], rank: Callable, leq: Callable) -> list[tuple[int, int]]:
    """Cover relations of a graded poset, as index pairs (lower, upper)."""
    by = {}
    for i, x in enumerate(elements):
        by.setdefault(rank(x), []).append(i)
    return [(i, j) for r in sorted(by) if r + 1 in by
            for i in by[r] for j in by[r + 1] if leq(elements[i], elements[j])]


def order_complex_facets(n: int, ranks: list[int], hasse: list[tuple[int, int]]) -> list[list[int]]:
    """Maximal chains of a graded poset given by its covers (all maximal chains start at rank 0)."""
    up = {i: [] for i in range(n)}
    for a, b in hasse:
        up[a].append(b)
    out = []
    def extend(chain):
        if not up[chain[-1]]:
            out.append(sorted(chain)); return
        for b in up[chain[-1]]:
            extend(chain + [b])
    for i in range(n):
        if ranks[i] == 0:
            extend([i])
    return out


def rank_cells(ranks: list[int]) -> list[list[int]]:
    return [[i for i, r in enumerate(ranks) if r == k] for k in range(max(ranks) + 1)]

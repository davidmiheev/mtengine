"""nauty adapter (dreadnaut): canonical forms of vertex-coloured graphs."""
from __future__ import annotations

import re

from ..core import EngineError, run_process, tail


def canonical_form(n: int, edges: list[tuple[int, int]], cells: list[list[int]] | None = None,
                   timeout: float = 600) -> str:
    """Canonical form of the undirected graph on 0..n-1, with the ordered vertex partition
    `cells` (colour classes; the order of cells is part of the input). Two coloured graphs are
    isomorphic (colour classes matched in order) iff their canonical forms are equal."""
    adj = {i: set() for i in range(n)}
    for a, b in edges:
        if a != b:
            adj[a].add(b); adj[b].add(a)
    lines = [f"n={n} g"] + [f"{i}:{' '.join(map(str, sorted(adj[i])))};" for i in range(n)]
    lines[-1] = lines[-1].rstrip(";") + "."
    cells = cells or [list(range(n))]
    part = "|".join(",".join(map(str, c)) for c in cells if c)
    script = "\n".join(lines) + f"\nf=[{part}]\n-a -m c x b\n"
    r, _ = run_process(["dreadnaut"], stdin=script, timeout=timeout)
    rows = re.findall(r"^\s*\d+\s*:\s*([^;]*);", r.stdout, re.M)
    if r.returncode != 0 or len(rows) != n:
        raise EngineError(f"dreadnaut failed:\n{tail(r.stdout + r.stderr)}")
    sizes = ",".join(str(len(c)) for c in cells)
    return f"cells[{sizes}]|" + "|".join(" ".join(row.split()) for row in rows)

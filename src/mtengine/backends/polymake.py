"""polymake adapter (topaz): integral homology of simplicial complexes."""
from __future__ import annotations

import json
import re

from ..core import EngineError, run_process, tail

_SCRIPT = r'''
use application "topaz";
use JSON::PP;
open my $fh, "<", "facets.json" or die; local $/; my $F = decode_json(<$fh>); close $fh;
my $K = new SimplicialComplex(FACETS => $F);
print "FVEC ", join(" ", @{$K->F_VECTOR}), "\n";
for my $g (@{$K->HOMOLOGY}) {
  print "H ", $g->betti_number, " ", join(";", map { $_->first . "^" . $_->second } @{$g->torsion}), "\n";
}
'''


def homology(facets: list[list[int]], timeout: float = 3600) -> dict:
    """Reduced integral homology of the complex with the given facets.

    Returns {"f_vector", "reduced_betti", "torsion"}; torsion[k] lists (order, multiplicity).
    """
    r, _ = run_process(["polymake", "--script", "{dir}/h.pl"],
                       files={"h.pl": _SCRIPT, "facets.json": json.dumps(facets)}, timeout=timeout)
    if r.returncode != 0 or "FVEC" not in r.stdout:
        raise EngineError(f"polymake failed (exit {r.returncode}):\n{tail(r.stderr or r.stdout)}")
    fvec = [int(x) for x in re.search(r"^FVEC (.*)$", r.stdout, re.M).group(1).split()]
    betti, torsion = [], []
    for line in re.findall(r"^H (.*)$", r.stdout, re.M):
        b, _, t = line.partition(" ")
        betti.append(int(b))
        torsion.append([[int(x) for x in p.split("^")] for p in t.split(";") if p])
    return {"f_vector": fvec, "reduced_betti": betti, "torsion": torsion}

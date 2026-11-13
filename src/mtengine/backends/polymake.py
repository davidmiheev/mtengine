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


_POLYTOPE = r'''
use application "polytope";
use JSON::PP;
open my $fh, "<", "in.json" or die; local $/; my $in = decode_json(<$fh>); close $fh;
my $hom = sub { [ map { [ map { new Rational($_) } @$_ ] } @{$_[0]} ] };
my $P = defined $in->{points}
  ? new Polytope<Rational>(POINTS => $hom->($in->{points}))
  : new Polytope<Rational>(INEQUALITIES => $hom->($in->{inequalities}),
                           defined $in->{equations} ? (EQUATIONS => $hom->($in->{equations})) : ());
print "FEASIBLE ", ($P->FEASIBLE ? 1 : 0), "\n";
exit 0 unless $P->FEASIBLE;
print "BOUNDED ", ($P->BOUNDED ? 1 : 0), "\n";
exit 0 unless $P->BOUNDED;
print "DIM ", $P->DIM, "\n";
print "AMBIENT ", $P->AMBIENT_DIM, "\n";
print "FVEC ", join(" ", @{$P->F_VECTOR}), "\n";
print "SIMPLE ", ($P->SIMPLE ? 1 : 0), "\n";
print "SIMPLICIAL ", ($P->SIMPLICIAL ? 1 : 0), "\n";
print "HVEC ", join(" ", @{$P->H_VECTOR}), "\n" if $P->SIMPLICIAL;
print "VOLUME ", $P->VOLUME, "\n" if $P->FULL_DIM;
print "VERTICES ", join(";", map { join(" ", @$_) } @{rows($P->VERTICES)}), "\n";
my $lat = $P->LATTICE;
print "LATTICE ", ($lat ? 1 : 0), "\n";
if ($lat) {
  print "NLP ", $P->N_LATTICE_POINTS, "\n";
  print "NILP ", $P->N_INTERIOR_LATTICE_POINTS, "\n";
  print "EHRHART ", join(" ", @{$P->EHRHART_POLYNOMIAL->coefficients_as_vector}), "\n";
  print "LVOL ", $P->LATTICE_VOLUME, "\n";
}
'''


def _rat(x: str):
    from fractions import Fraction
    q = Fraction(x)
    return q.numerator if q.denominator == 1 else str(q)


def polytope(points=None, inequalities=None, equations=None, timeout: float = 3600) -> dict:
    """Combinatorics and Ehrhart data of a polytope from its points (V-description) or from
    inequalities b + a.x >= 0 given as [b, a_1, ..., a_d] (H-description, optional equations
    in the same form). Entries are integers or rational strings."""
    if (points is None) == (inequalities is None):
        raise EngineError("give exactly one of points or inequalities")
    if points is not None:
        data = {"points": [["1", *map(str, p)] for p in points]}
    else:
        data = {"inequalities": [[str(x) for x in row] for row in inequalities]}
        if equations:
            data["equations"] = [[str(x) for x in row] for row in equations]
    r, _ = run_process(["polymake", "--script", "{dir}/p.pl"],
                       files={"p.pl": _POLYTOPE, "in.json": json.dumps(data)}, timeout=timeout)
    if r.returncode != 0 or "FEASIBLE" not in r.stdout:
        raise EngineError(f"polymake failed (exit {r.returncode}):\n{tail(r.stderr or r.stdout)}")
    kv = dict(l.split(" ", 1) if " " in l else (l, "") for l in r.stdout.splitlines()
              if re.match(r"^[A-Z]+( |$)", l))
    if kv["FEASIBLE"] != "1":
        return {"feasible": False}
    if kv["BOUNDED"] != "1":
        return {"feasible": True, "bounded": False}
    ints = lambda k: [int(x) for x in kv[k].split()]
    out = {"feasible": True, "bounded": True, "dim": int(kv["DIM"]), "ambient_dim": int(kv["AMBIENT"]),
           "f_vector": ints("FVEC"), "simple": kv["SIMPLE"] == "1",
           "simplicial": kv["SIMPLICIAL"] == "1",
           "vertices": [[_rat(x) for x in v.split()[1:]] for v in kv["VERTICES"].split(";") if v],
           "volume": _rat(kv["VOLUME"]) if "VOLUME" in kv else None,
           "lattice": kv["LATTICE"] == "1"}
    out["n_vertices"] = len(out["vertices"])
    out["n_facets"] = out["f_vector"][-1] if out["f_vector"] else 0
    out["h_vector"] = ints("HVEC") if "HVEC" in kv else None
    out["h_vector_dual"] = _dual_h(out["f_vector"]) if out["simple"] else None
    if out["lattice"]:
        out.update(n_lattice_points=int(kv["NLP"]), n_interior_lattice_points=int(kv["NILP"]),
                   ehrhart_polynomial=[_rat(x) for x in kv["EHRHART"].split()],
                   normalized_volume=_rat(kv["LVOL"]))
    return out


def _dual_h(f: list[int]) -> list[int]:
    """h-vector of the dual simplicial polytope of a simple polytope, from its f-vector
    f = (f_0, ..., f_{d-1}) (f_i = number of i-dimensional faces): sum_i h_i t^i =
    sum_i f_i (t - 1)^i with f_d = 1. For a simple lattice polytope these are the even Betti
    numbers of the projective toric variety (and of any quasitoric manifold) over it."""
    from math import comb
    fs = list(f) + [1]
    d = len(fs) - 1
    h = [0] * (d + 1)
    for i, fi in enumerate(fs):
        for k in range(i + 1):
            h[k] += fi * comb(i, k) * (-1) ** (i - k)
    return h

"""Regina backend against known values. These call the real tool (via regina-python)."""
import json

import pytest
from mtengine import api, core

POINCARE = "fvPQcdecedekrsnrs"          # Poincare homology sphere
FIG8_COMPLEMENT = "cPcbbbiht"           # SnapPea census m004
M003 = "cPcbbbdxm"                      # Regina's census triangulation of m003
WEEKS_CLOSED = "jLvMLQQbfefgihhiixiptvvvgof"   # closed census: 0.94270... : m003(-3, 1)
CP2 = "eAMMcaabccdd+aoa+aAaqbqbGa"
S2XS2 = "gALAMQaacdcdeeffPbgaVbaaJafbyaJafbva"
FIG8_PD = "PD[X[2, 7, 3, 8], X[4, 2, 5, 1], X[6, 3, 7, 4], X[8, 6, 1, 5]]"
WEEKS_VOLUME = 0.9427073627769277


def val(r):
    return r["value"]


def test_version():
    assert api.versions()["regina"].startswith("Regina ")


def test_regina_run():
    assert val(api.regina_run("print(regina.Example3.lens(7, 2).homology())")).strip() == "Z_7"


def test_invariants_and_recognition_poincare():
    r = val(api.triangulation_invariants(POINCARE, recognise=True))
    assert (r["closed"], r["orientable"], r["homology"]["H1"]) == (True, True, "0")
    assert r["recognition"]["sphere"] is False and r["recognition"]["irreducible"] is True
    assert any(c["name"].startswith("SFS [S2: (2,1) (3,1) (5,-4)]") for c in r["census"])


def test_invariants_dimension_4():
    cp2 = val(api.triangulation_invariants(CP2, dim=4))
    assert cp2["euler_char"] == 3 and cp2["homology"]["H2"] == "Z"
    assert cp2["intersection_form"] == {"rank": 1, "signature": 1, "even": False,
                                        "matrix": [[1]]}
    form = val(api.triangulation_invariants(S2XS2, dim=4))["intersection_form"]
    assert (form["rank"], form["signature"], form["even"]) == (2, 0, True)


def test_census_lookup():
    names = {h["name"] for h in val(api.census_lookup(FIG8_COMPLEMENT))}
    assert "m004 : #1" in names


def test_hyperbolic_cusped_and_filled():
    r = val(api.hyperbolic_structure(FIG8_COMPLEMENT))
    assert r["solution"] == "Geometric" and abs(r["volume"] - 2.0298832128193) < 1e-9
    # The Weeks manifold as a Dehn filling of m003; Regina's m003 uses the census slopes.
    w = val(api.hyperbolic_structure(M003, fillings=[[-3, 1]]))
    assert w["volume_trustworthy"] and abs(w["volume"] - WEEKS_VOLUME) < 1e-9
    assert w["homology_filled"] == "2 Z_5"   # H1(Weeks) = Z_5 + Z_5, in Regina's notation


def test_hyperbolic_closed_triangulation_is_retried():
    # SnapPea's handling of closed triangulations is random; the adapter retries until the
    # solution is non-degenerate, and then the volume is right.
    w = val(api.hyperbolic_structure(WEEKS_CLOSED, use_cache=False))
    assert w["volume_trustworthy"] and abs(w["volume"] - WEEKS_VOLUME) < 1e-9
    assert 1 <= w["attempts"] <= 20


def test_turaev_viro_roots_match_regina_approx():
    tv = val(api.turaev_viro(POINCARE, 5))
    assert set(tv["exact"]) == {"odd_w", "even_w"} and set(tv["by_root"]) == {"1", "2", "3", "4"}
    # Independent check of the root bookkeeping against turaevViroApprox(r, w).
    approx = json.loads(val(api.regina_run(
        "import json; t = regina.Triangulation3.fromIsoSig('%s');"
        "print(json.dumps({w: t.turaevViroApprox(5, w) for w in (1, 2, 3, 4)}))" % POINCARE)))
    for w, x in approx.items():
        assert abs(tv["by_root"][w] - x) < 1e-9, w
    assert val(api.turaev_viro("bkaagj", 5))["exact"] != val(api.turaev_viro("cMcabbjxr", 5))["exact"]


def test_link_invariants():
    k = val(api.link_invariants(FIG8_PD))
    assert k["jones"] == "x^4 - x^2 + 1 - x^-2 + x^-4" and k["alexander"] == "x^2 - 3 x + 1"
    assert any(c["name"].startswith("m004") for c in k["complement"]["census"])
    t = val(api.link_invariants("4 6 2", format="dt", complement=False))
    assert t["crossings"] == 3 and t["components"] == 1 and "complement" not in t
    # Codes may also be lists.
    assert val(api.link_invariants([4, 6, 2], format="dt", complement=False))["jones"] == t["jones"]
    pd = [[2, 7, 3, 8], [4, 2, 5, 1], [6, 3, 7, 4], [8, 6, 1, 5]]
    assert val(api.link_invariants(pd, complement=False))["jones"] == k["jones"]


def test_normal_surfaces():
    s = val(api.normal_surfaces(FIG8_COMPLEMENT, coords="quad"))
    assert s["count"] == 4 and len(s["surfaces"]) == 4 and not s["truncated"]
    # The figure-eight complement is ideal: its quad vertex surfaces include spun ones.
    assert any(not x["compact"] for x in s["surfaces"])
    # A one-tetrahedron (layered) S3: the vertex-linking sphere and a Heegaard torus.
    s3 = val(api.normal_surfaces("bkaagj", coords="standard"))
    assert s3["count"] == 2
    assert sorted((x["euler_char"], x["vertex_link"], x["orientable"], x["two_sided"])
                  for x in s3["surfaces"]) == [(0, False, True, True), (2, True, True, True)]


def test_errors_are_reported():
    with pytest.raises(core.EngineError, match="regina"):
        api.triangulation_invariants("not-a-signature", use_cache=False)
    with pytest.raises(core.EngineError, match="unknown link format"):
        api.link_invariants("x", format="nope", use_cache=False)


def test_pachner_walk_is_reproducible():
    a = val(api.pachner_walk(POINCARE, moves=10, seeds=[1, 2], use_cache=False))
    b = val(api.pachner_walk(POINCARE, moves=10, seeds=[1, 2], use_cache=False))
    assert a == b and [w["size"] for w in a] == [15, 15] and a[0]["isosig"] != a[1]["isosig"]


def test_simplify_greedy_and_exhaustive():
    walk = val(api.pachner_walk(POINCARE, moves=8, seeds=[3]))
    r = val(api.simplify_triangulations([walk[0]["isosig"]], trials=2, lookup=True))[0]
    assert r["input_size"] == 13 and r["final_size"] == 5
    assert any(n.startswith("SFS [S2: (2,1) (3,1) (5,-4)]") for n in r["census"])
    # A 9-tetrahedron 3-sphere from E02 of regina_experiments: greedy simplify() never
    # reduces it; exhaustive search at height 2 does.
    hard = val(api.simplify_triangulations(["jLLvQPQbeghfifiihxxaaxxjxar"], trials=3,
                                           max_height=2, target_size=1))[0]
    assert hard["greedy_best"] == 9 and hard["final_size"] == 1
    assert [s["height"] for s in hard["exhaustive"]] == [1, 2]


def test_pachner_walk_from_one_tetrahedron():
    # The one-tetrahedron 3-sphere has no 2-3 move; the walk starts with a 1-4 move.
    w = val(api.pachner_walk("bkaagj", moves=3, seeds=[0]))[0]
    assert w["size"] == 1 + 3 + 2
    r = val(api.simplify_triangulations([w["isosig"]], trials=3, max_height=2, target_size=1))[0]
    assert r["final_size"] == 1

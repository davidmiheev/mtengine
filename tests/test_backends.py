"""Each backend against known values. These call the real tools."""
import pytest
from mtengine import api


def val(r):
    return r["value"]


def test_versions_present():
    v = api.versions()
    for tool in ["macaulay2", "gfan", "polymake", "singular", "nauty", "lean"]:
        assert v[tool] not in ("MISSING", "UNAVAILABLE"), tool


# ---- Macaulay2: the GKM computation must agree with the BB formula, including partial cases
@pytest.mark.parametrize("kbar,h", [
    ((2, 2), (2, 2)),             # Gr(2,4)
    ((1, 2, 2), (2, 3, 3)),       # partial Hessenberg
    ((2, 1, 2), (3, 3, 3)),       # partial flag variety Fl_(2,1,2)
    ((1, 1, 1, 1), (2, 3, 4, 4)), # permutohedral variety
])
def test_gkm_matches_bb(kbar, h):
    assert val(api.hessenberg_betti_gkm(list(kbar), list(h)))["betti"] == val(api.hessenberg_betti(list(kbar), list(h)))


@pytest.mark.slow
def test_gkm_counterexample_pair():
    assert val(api.hessenberg_betti_gkm([1] * 5, [2, 3, 5, 5, 5]))["betti"] == [1, 17, 42, 42, 17, 1]


# ---- gfan
def test_tropical_flag_variety_fl3():
    r = val(api.tropical_variety(["p1", "p2", "p3", "p12", "p13", "p23"], ["p3*p12-p2*p13+p1*p23"]))
    assert (r["dim"], r["lineality_dim"], r["f_vector"]) == (5, 4, [1, 3])  # prefix names handled


# ---- polymake
def test_homology_circle_and_rp2():
    assert val(api.simplicial_homology([[0, 1], [1, 2], [0, 2]]))["reduced_betti"] == [0, 1]
    rp2 = [[0,1,2],[0,2,3],[0,3,4],[0,1,5],[0,4,5],[1,2,4],[1,3,4],[1,3,5],[2,3,5],[2,4,5]]
    r = val(api.simplicial_homology(rp2))
    assert r["reduced_betti"] == [0, 0, 0] and r["torsion"][1] == [[2, 1]]


def test_face_poset_homology_fl3():
    # Cl(K_3) minus top is the subdivided GKM graph K_{3,3}: reduced Betti (0, 4)
    assert val(api.hessenberg_face_poset_homology([1, 1, 1], [3, 3, 3]))["reduced_betti"] == [0, 4]


# ---- nauty
def test_canonical_forms():
    a = val(api.graph_canonical_form(4, [[0, 1], [1, 2], [2, 3]]))
    b = val(api.graph_canonical_form(4, [[2, 0], [0, 3], [3, 1]]))   # relabelled path
    c = val(api.graph_canonical_form(4, [[0, 1], [0, 2], [0, 3]]))   # star
    assert a == b and a != c


def test_canonical_forms_traces():
    from mtengine.backends.nauty import canonical_form
    path1 = canonical_form(4, [(0, 1), (1, 2), (2, 3)], algorithm="traces")
    path2 = canonical_form(4, [(2, 0), (0, 3), (3, 1)], algorithm="traces")
    star = canonical_form(4, [(0, 1), (0, 2), (0, 3)], algorithm="traces")
    assert path1 == path2 and path1 != star
    assert path1.startswith("traces:")


def test_face_poset_isomorphism():
    # Fl_(1,2) and Fl_(2,1) are both CP^2 with the same torus action: isomorphic face posets
    p = val(api.hessenberg_face_poset_canonical([1, 2], [2, 2]))
    q = val(api.hessenberg_face_poset_canonical([2, 1], [2, 2]))
    r = val(api.hessenberg_face_poset_canonical([2, 2], [2, 2]))
    assert p == q and p != r


# ---- Singular
def test_singular():
    out = val(api.singular_run("ring r = 0,(x,y),dp; ideal i = x2-y3, xy; print(vdim(std(i)));"))
    assert out.strip() == "5"


# ---- Lean
def test_lean_g2_is_sorry_free():
    r = val(api.lean_check("import Formal", ["MatroidToric.span_prod_eq_iff", "MatroidToric.vectorMatroid_indep_iff"]))
    assert r["ok"] and not r["uses_sorry"]
    assert set(r["axioms"]["MatroidToric.span_prod_eq_iff"]) == {"propext", "Classical.choice", "Quot.sound"}


def test_lean_detects_sorry_and_errors():
    r = val(api.lean_check("theorem t : 1 + 1 = 3 := by sorry", ["t"]))
    assert r["uses_sorry"] == ["t"]
    assert not val(api.lean_check("theorem u : (2 : Nat) = 3 := rfl"))["ok"]


# ---- cache and jobs
def test_cache_and_provenance():
    first = api.hessenberg_betti([2, 2], [2, 2], use_cache=False)
    again = api.hessenberg_betti([2, 2], [2, 2])
    again2 = api.hessenberg_betti([2, 2], [2, 2])
    assert again2["cached"] and again2["value"] == first["value"]
    assert first["provenance"]["backend"] == "python" and len(first["provenance"]["input_sha256"]) == 64


def test_job_queue():
    import time
    jid = api.job_submit("hessenberg_betti", {"kbar": [1, 1, 1], "h": [3, 3, 3]})["job_id"]
    for _ in range(100):
        st = api.job_status(jid)
        if st["state"] in ("done", "error"):
            break
        time.sleep(0.1)
    assert st["state"] == "done" and st["result"]["value"] == [1, 2, 2, 1]

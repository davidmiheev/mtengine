"""Each backend against known values. These call the real tools."""
import json
from pathlib import Path

import pytest
from mtengine import api
from mtengine.core import EngineError


def val(r):
    return r["value"]


def test_versions_present():
    v = api.versions()
    for tool in ["macaulay2", "gfan", "polymake", "singular", "nauty", "lean", "regina"]:
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


# ---- Lean (needs a ready Lake project with Mathlib: `mte lean-init`, or matroid_toric's formal/)
from mtengine.backends import lean as _lean

_LEAN = _lean.status()
needs_lean = pytest.mark.skipif(not _LEAN["ready"], reason=f"Lean: {_LEAN['problem']}")
needs_formal = pytest.mark.skipif(not _LEAN["ready"] or not (Path(_LEAN["project"]) / "Formal.lean").exists(),
                                  reason="needs matroid_toric's formal/ project")
needs_mathlib = pytest.mark.skipif(not _LEAN["ready"] or not _LEAN["mathlib"], reason="needs Mathlib")


@needs_formal
def test_lean_g2_is_sorry_free():
    r = val(api.lean_check("import Formal", ["MatroidToric.span_prod_eq_iff", "MatroidToric.vectorMatroid_indep_iff"]))
    assert r["ok"] and not r["uses_sorry"]
    assert set(r["axioms"]["MatroidToric.span_prod_eq_iff"]) == {"propext", "Classical.choice", "Quot.sound"}


@needs_lean
def test_lean_detects_sorry_and_errors():
    r = val(api.lean_check("theorem t : 1 + 1 = 3 := by sorry", ["t"]))
    assert r["uses_sorry"] == ["t"]
    assert not val(api.lean_check("theorem u : (2 : Nat) = 3 := rfl"))["ok"]


@needs_mathlib
@pytest.mark.slow
def test_lean_check_with_mathlib():
    r = val(api.lean_check("import Mathlib\ntheorem v : (2 : ℚ) + 2 = 4 := by norm_num", ["v"]))
    assert r["ok"] and not r["uses_sorry"]
    assert set(r["axioms"]["v"]) <= {"propext", "Classical.choice", "Quot.sound"}
    assert r["project"]["path"] == _LEAN["project"] and r["project"]["mathlib"] == _LEAN["mathlib"]


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


# ---- which Lean project (no Lean needed: fake Lake projects in tmp_path)
def _lake_project(p, mathlib=None, built=False):
    p.mkdir(parents=True)
    (p / "lean-toolchain").write_text("leanprover/lean4:v4.36.0-rc1\n")
    (p / "lakefile.toml").write_text('name = "x"\n')
    if mathlib:
        (p / "lake-manifest.json").write_text(json.dumps({"packages": [{"name": "mathlib", "rev": mathlib}]}))
    if built:
        olean = p / ".lake" / "packages" / "mathlib" / ".lake" / "build" / "lib" / "lean" / "Mathlib.olean"
        olean.parent.mkdir(parents=True)
        olean.write_bytes(b"")
    return p


@pytest.fixture
def lean_sandbox(tmp_path, monkeypatch):
    from mtengine.backends import lean
    monkeypatch.delenv("MTENGINE_LEAN_PROJECT", raising=False)
    monkeypatch.setattr(lean, "SIBLING_PROJECT", tmp_path / "formal")
    monkeypatch.setattr(lean, "DATA_PROJECT", tmp_path / "data")
    monkeypatch.setattr(lean, "_lake", lambda: "/usr/bin/lake")
    return lean, tmp_path


def test_lean_resolution_order(lean_sandbox, monkeypatch):
    lean, tmp = lean_sandbox
    st = lean.status()
    assert st["project"] is None and not st["ready"] and "mte lean-init" in st["problem"]
    assert lean.version().startswith("MISSING") and not st["skipped"]
    _lake_project(tmp / "data", "a" * 40, built=True)
    assert lean.status()["source"] == "standard" and lean.status()["ready"]       # `mte lean-init`
    _lake_project(tmp / "formal", "b" * 40, built=True)
    assert lean.status()["source"] == "sibling"                                    # matroid_toric layout
    _lake_project(tmp / "p", "c" * 40, built=True)
    monkeypatch.setenv("MTENGINE_LEAN_PROJECT", str(tmp / "x" / ".." / "p"))
    st = lean.status()
    assert st["source"] == "MTENGINE_LEAN_PROJECT" and st["project"] == str((tmp / "p").resolve())
    assert st["mathlib"] == "c" * 40 and lean.project() == (tmp / "p").resolve()


def test_lean_env_var_to_a_missing_directory_is_skipped(lean_sandbox, monkeypatch):
    """The disagreement this replaces: the variable named a directory that did not exist,
    versions() said MISSING, but lean_check still tried (and created directories there)."""
    lean, tmp = lean_sandbox
    monkeypatch.setenv("MTENGINE_LEAN_PROJECT", str(tmp / "nowhere" / "formal"))
    st = lean.status()
    assert st["project"] is None and not st["ready"]
    assert st["skipped"] == [{"source": "MTENGINE_LEAN_PROJECT", "path": str(tmp / "nowhere" / "formal"),
                              "reason": "no such directory"}]
    with pytest.raises(EngineError, match="no Lean project"):
        lean.check("theorem t : True := trivial")
    assert not (tmp / "nowhere").exists()
    _lake_project(tmp / "data", "a" * 40, built=True)
    assert lean.status()["source"] == "standard" and lean.status()["ready"]       # falls through


def test_lean_not_a_lake_project_or_not_built(lean_sandbox, monkeypatch):
    lean, tmp = lean_sandbox
    (tmp / "p").mkdir()
    (tmp / "p" / "lean-toolchain").write_text("leanprover/lean4:v4.36.0-rc1\n")
    monkeypatch.setenv("MTENGINE_LEAN_PROJECT", str(tmp / "p"))
    assert lean.status()["skipped"][0]["reason"] == "no lakefile.toml or lakefile.lean"
    _lake_project(tmp / "data", "a" * 40, built=False)
    st = lean.status()
    assert st["source"] == "standard" and not st["ready"] and "`mte lean-init`" in st["problem"]
    assert lean.version().startswith("MISSING (Mathlib is not built")
    with pytest.raises(EngineError, match="Mathlib is not built"):
        lean.check("theorem t : True := trivial")
    # an explicitly chosen Lake project is used even when not built: no silent fallback
    _lake_project(tmp / "q", "b" * 40, built=False)
    monkeypatch.setenv("MTENGINE_LEAN_PROJECT", str(tmp / "q"))
    st = lean.status()
    assert st["source"] == "MTENGINE_LEAN_PROJECT" and "lake exe cache get" in st["problem"]


def test_lean_check_raises_when_lean_cannot_run(lean_sandbox, monkeypatch):
    """A tool failure (no toolchain, lake crash) is an error, not a proof that failed."""
    from mtengine.core import Run
    lean, tmp = lean_sandbox
    _lake_project(tmp / "data", "a" * 40, built=True)
    monkeypatch.setattr(lean, "run_process", lambda *a, **k: (
        Run(1, "", "error: no default toolchain configured. run `elan default stable`", 0.1), tmp))
    with pytest.raises(EngineError, match="lake env lean failed"):
        lean.check("theorem t : True := trivial")
    monkeypatch.setattr(lean, "run_process", lambda *a, **k: (
        Run(1, "MteCheck_x.lean:1:0: error: unknown identifier 'foo'\n", "", 0.1), tmp))
    r = lean.check("example := foo")
    assert not r["ok"] and r["errors"] and r["project"]["source"] == "standard"


def test_lean_fingerprint_follows_the_projects_own_files(lean_sandbox):
    lean, tmp = lean_sandbox
    p = _lake_project(tmp / "data", "a" * 40, built=True)
    (p / "Formal").mkdir()
    (p / "Formal" / "A.lean").write_text("theorem a : True := by sorry\n")
    f0 = lean.fingerprint()
    (p / ".lake" / "packages" / "mathlib" / "Junk.lean").write_text("-- dependency, not ours\n")
    assert lean.fingerprint() == f0
    (p / "Formal" / "A.lean").write_text("theorem a : True := trivial\n")      # sorry removed
    assert lean.fingerprint() != f0


def test_lean_pinned_spec_is_consistent():
    """The standard project's spec shipped in the package: an exact Mathlib commit, required by
    the lakefile at the tag the manifest was made from, and Mathlib's toolchain."""
    import tomllib
    from mtengine.backends import lean
    for f in lean.PINNED_FILES:
        assert (lean.PINNED / f).is_file(), f
    manifest = json.loads((lean.PINNED / "lake-manifest.json").read_text())
    ml = next(q for q in manifest["packages"] if q["name"] == "mathlib")
    req = next(q for q in tomllib.loads((lean.PINNED / "lakefile.toml").read_text())["require"]
               if q["name"] == "mathlib")
    assert len(ml["rev"]) == 40 and req["rev"] == ml["inputRev"]
    assert lean.pinned() == {"toolchain": (lean.PINNED / "lean-toolchain").read_text().strip(),
                             "mathlib": ml["rev"]}
    assert lean.pinned()["toolchain"].startswith("leanprover/lean4:")


def test_dockerfile_names_the_backend_packages():
    """Installers outside Docker (the "math" cloud environment's setup script) take the backend
    apt packages from the Dockerfile's single ARG APT_BACKENDS="..." line, with this pattern."""
    import re
    text = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text()
    lines = re.findall(r'^ARG APT_BACKENDS="(.*)"$', text, re.M)
    assert len(lines) == 1
    assert {"macaulay2", "gfan", "polymake", "singular", "nauty", "normaliz"} <= set(lines[0].split())
    assert "install -y --no-install-recommends $APT_BACKENDS" in text      # and Docker uses it

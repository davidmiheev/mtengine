"""Matroids, hyperplane arrangements (pure Python) and polytopes (polymake), against known values."""
from itertools import combinations

import pytest
from mtengine import api
from mtengine.domain import matroids as mt


def val(r):
    return r["value"]


def braid(n):
    """Normals e_i - e_j of the braid arrangement A_{n-1}: the graphic matroid of K_n."""
    return [[1 if k == i else -1 if k == j else 0 for k in range(n)] for i, j in combinations(range(n), 2)]


def test_uniform_u24():
    r = val(api.matroid_invariants([[1, 0], [0, 1], [1, 1], [1, -1]], oriented=True))
    assert r["rank"] == 2 and r["simple"] and r["flats_by_rank"] == [1, 4, 1]
    assert r["characteristic_polynomial"] == [3, -4, 1]          # t^2 - 4t + 3
    assert r["poincare_polynomial"] == [1, 4, 3]
    assert r["beta_invariant"] == 2 and r["n_bases"] == 6
    assert r["tutte_polynomial"] == {"0,1": 2, "0,2": 1, "1,0": 2, "2,0": 1}   # x^2+2x+2y+y^2
    assert r["chirotope"]["chirotope"] == "++----"


def test_k5_graphic():
    r = val(api.matroid_invariants(braid(5)))
    assert r["characteristic_polynomial"] == [24, -50, 35, -10, 1]   # (t-1)(t-2)(t-3)(t-4)
    assert r["n_bases"] == 125                                         # Cayley: 5^3 spanning trees
    assert r["flats_by_rank"] == [1, 10, 25, 15, 1]                    # set partitions of [5]


def test_loops_parallels_and_rationals():
    r = val(api.matroid_invariants([[0, 0], [1, 0], ["1/2", 0], [0, 3]]))
    assert r["loops"] == [0] and r["parallel_classes"] == [[1, 2]] and not r["simple"]
    assert r["characteristic_polynomial"] == [0, 0, 0]               # a loop kills chi
    assert [0] in r["circuits"] and [1, 2] in r["circuits"]


def test_tutte_specialisations():
    r = val(api.matroid_invariants(braid(4)))
    T = {tuple(map(int, k.split(","))): c for k, c in r["tutte_polynomial"].items()}
    assert sum(T.values()) == r["n_bases"] == 16                      # T(1,1) = 4^2 spanning trees
    assert sum(c * 2 ** i for (i, j), c in T.items() if j == 0) == 24  # T(2,0) = acyclic orientations


@pytest.mark.parametrize("n", [3, 4])
def test_orlik_solomon_matches_flats(n):
    r = val(api.orlik_solomon(braid(n)))
    assert r["agrees"]
    assert r["hilbert_function"] == {3: [1, 3, 2], 4: [1, 6, 11, 6]}[n]   # Arnold: (1+t)(1+2t)...


def test_braid_arrangement():
    r = val(api.hyperplane_arrangement(braid(4)))
    assert r["characteristic_polynomial"] == [0, -6, 11, -6, 1]      # t(t-1)(t-2)(t-3)
    assert r["regions"] == 24 and r["bounded_regions"] == 0           # Weyl chambers of S_4
    assert r["complement_betti"] == [1, 6, 11, 6]


def test_affine_arrangements():
    r = val(api.hyperplane_arrangement([[1, 0], [0, 1], [1, 1]], [0, 0, 1]))   # three generic lines
    assert (r["regions"], r["bounded_regions"]) == (7, 1)
    assert r["intersection_poset_by_rank"] == [1, 3, 3]
    r = val(api.hyperplane_arrangement([[1, 0], [2, 0], [0, 1]], [0, 2, 0]))   # x=0, x=1, y=0
    assert (r["n_hyperplanes"], r["regions"], r["bounded_regions"]) == (3, 6, 0)
    r = val(api.hyperplane_arrangement([[1, 0], [2, 0]], [1, 2]))              # the same line twice
    assert r["n_hyperplanes"] == 1 and r["regions"] == 2


def test_parse_errors():
    with pytest.raises(mt.EngineError):
        mt.parse_vectors([[1, 2], [3]])
    with pytest.raises(mt.EngineError):
        api.hyperplane_arrangement([[0, 0]], use_cache=False)


# ---- polymake polytopes
def test_hexagon_permutohedron():
    perms = [[1, 2, 3], [1, 3, 2], [2, 1, 3], [2, 3, 1], [3, 1, 2], [3, 2, 1]]
    r = val(api.polytope_invariants(points=perms))
    assert (r["dim"], r["ambient_dim"], r["f_vector"]) == (2, 3, [6, 6])
    assert r["simple"] and r["h_vector_dual"] == [1, 4, 1]           # Betti numbers of Fl(C^3)
    assert r["ehrhart_polynomial"] == [1, 3, 3] and r["n_interior_lattice_points"] == 1


def test_simple_3_polytopes():
    cube = [[x, y, z] for x in (0, 1) for y in (0, 1) for z in (0, 1)]
    r = val(api.polytope_invariants(points=cube))
    assert r["f_vector"] == [8, 12, 6] and r["h_vector_dual"] == [1, 3, 3, 1]   # (CP^1)^3
    assert r["volume"] == 1 and r["ehrhart_polynomial"] == [1, 3, 3, 1]


def test_h_description_and_rationals():
    r = val(api.polytope_invariants(inequalities=[[0, 1, 0], [0, 0, 1], [2, -1, -1]]))   # 2 * simplex
    assert r["vertices"] and r["n_lattice_points"] == 6 and r["normalized_volume"] == 4
    r = val(api.polytope_invariants(points=[[0, 0], [1, 0], [0, "1/2"]]))
    assert not r["lattice"] and r["volume"] == "1/4"
    assert val(api.polytope_invariants(inequalities=[[-1, 1], [-1, -1]])) == {"feasible": False}

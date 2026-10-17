"""Pure-Python mathematics, checked against known values."""
from math import comb
from mtengine.domain import hessenberg as hs


def q_factorial(n):
    poly = [1]
    for m in range(1, n + 1):
        new = [0] * (len(poly) + m - 1)
        for i, a in enumerate(poly):
            for j in range(m):
                new[i + j] += a
        poly = new
    return poly


def test_full_flag_is_q_factorial():
    for n in (3, 4, 5):
        assert hs.betti((1,) * n, (n,) * n) == q_factorial(n)


def test_grassmannians():
    assert hs.betti((2, 2), (2, 2)) == [1, 1, 2, 1, 1]          # Gr(2,4)
    assert hs.betti((2, 3), (2, 2)) == [1, 1, 2, 2, 2, 1, 1]    # Gr(2,5)
    assert hs.faces_by_rank((2, 2), (2, 2)) == [6, 12, 11, 1]   # 12 = edges of the octahedron


def test_counterexample_pair():
    # thesis v2, Theorem 4.35
    assert hs.betti((1,) * 5, (2, 3, 5, 5, 5)) == [1, 17, 42, 42, 17, 1]
    assert hs.betti((1,) * 5, (2, 4, 4, 5, 5)) == [1, 12, 47, 47, 12, 1]


def test_euler_characteristic_and_dimension():
    for kbar, h in [((2, 2), (2, 2)), ((1, 2, 2), (2, 3, 3)), ((2, 1, 2), (3, 3, 3)), ((1, 1, 1, 1), (2, 4, 4, 4))]:
        b = hs.betti(kbar, h)
        n = sum(kbar)
        mult = 1
        for k in kbar:
            mult *= comb(n, k); n -= k
        assert sum(b) == mult                       # number of fixed points
        assert len(b) - 1 == hs.dimension(kbar, h)  # top degree = complex dimension
        assert b == b[::-1]                         # Poincare duality


def test_cover_counts_match_brute_force():
    for kbar, h in [((2, 2), (2, 2)), ((1, 2, 2), (2, 3, 3))]:
        E = hs.graph(h); F = hs.faces(kbar, h); n = sum(kbar)
        rk = {f: hs.face_rank(f, n) for f in F}
        for f in F:
            assert hs.lower_covers(f, E) == sum(1 for g in F if rk[g] == rk[f] - 1 and hs.face_leq(g, f))
            assert hs.upper_covers(f, E) == sum(1 for g in F if rk[g] == rk[f] + 1 and hs.face_leq(f, g))


def test_invalid_data_rejected():
    import pytest
    with pytest.raises(ValueError):
        hs.betti((2, 2), (2, 1))   # decreasing: not a Hessenberg function

# mtengine

An engine for **computational experiments in mathematics**, above all in **topology and
geometry**: torus actions and GKM theory, matroids and hyperplane arrangements,
polytopes and toric geometry, tropical geometry, combinatorial topology, and low-dimensional (3- and 4-manifold) topology. It puts one
interface — a Python API, the `mte` CLI and an MCP server for AI agents — in front of
**Macaulay2, gfan, polymake, Singular, nauty, Lean 4/Mathlib and Regina**, and records where
every result came from, so that an experiment can be cited, re-run and checked.

| Area | Backends | Typical use |
|---|---|---|
| Equivariant topology, GKM theory | Macaulay2, Python | Betti numbers from GKM graphs; Hessenberg varieties, their face posets |
| Commutative algebra, algebraic geometry | Macaulay2, Singular | ideals, Hilbert series, raw scripts |
| Tropical geometry | gfan | tropical varieties: dimension, lineality, f-vector |
| Combinatorial topology, polytopes | polymake | simplicial homology with torsion, order complexes of posets |
| Matroids, oriented matroids, hyperplane arrangements | Python (exact), Macaulay2 | lattice of flats, characteristic/Tutte polynomials, chirotopes and reorientation classes, Orlik–Solomon algebras, Chow rings and augmented Chow rings, Kazhdan–Lusztig polynomials; regions and Betti numbers of complements |
| Convex and toric geometry | polymake | f- and h-vectors, Ehrhart polynomials, lattice points; Betti numbers of toric varieties and quasitoric manifolds over simple polytopes |
| Combinatorics | nauty | canonical forms and isomorphism of coloured graphs and posets |
| Low-dimensional topology | Regina (+ SnapPea) | 3-/4-manifold triangulations, census, hyperbolic structures, Turaev–Viro, knot invariants, normal surfaces, Pachner moves |
| Formal verification | Lean 4 / Mathlib | compile a proof, list its axioms, flag `sorry` |

It started as the engine of [matroid_toric](https://github.com/davidmiheev/matroid_toric) (the
working repository for the paper *Face posets, local weight matroids and Betti numbers of torus
actions*), which still uses it as a git submodule at `engine/`; the history of `engine/` is
preserved here. The domain modules for that project (Hessenberg varieties, GKM graphs, face
posets) are one application among others, not the scope of the engine.

## Design

```
            Python API (mtengine.api)  ←  one source of truth: FUNCTIONS
              ↑                ↑                 ↑
         mte CLI         MCP server        your scripts / notebooks
                    (mtengine-mcp, stdio)
  ─────────────────────────────────────────────────────────────────
  core: process runner · result cache keyed by (backend, version, input) · provenance · job queue
  backends: macaulay2 · gfan · polymake · singular · nauty · lean · regina
  domain:   matroids (flats, arrangements, chirotopes) · hessenberg (fixed points, BB Betti
            numbers, GKM graphs, faces) · posets
```

- **Every result carries provenance**: backend and its version, engine version, function,
  SHA-256 of the input, wall time, timestamp. Results are cached under
  `~/.cache/mtengine` (override with `MTENGINE_CACHE`); the key includes the tool version, so
  upgrading a tool invalidates its results instead of silently reusing them.
- **Long computations** go through `job_submit` / `job_status` (MCP calls are request/response).
- **Known tool bugs are absorbed in the adapters**, not left to callers: gfan 0.6.2 aborts on
  variable names that are prefixes of each other (`p1`, `p12`), so the adapter renames to
  equal-length names and maps back.
  Regina likewise: SnapPea's handling of a closed triangulation is random and often
  degenerate, so `hyperbolic_structure` retries until the solution is non-degenerate (and says
  whether the volume can be trusted); `turaev_viro` evaluates even roots of unity correctly
  (Regina's documented formula is off by a factor of two in the root index).
- MCP is a front end, not the architecture: the same functions serve the CLI and scripts.

## Functions

`mte list` prints signatures. Highlights:

| Function | Backend | What |
|---|---|---|
| `gkm_betti` | Macaulay2 | Betti numbers of any GKM graph from the Hilbert series of its ring of graph functions |
| `tropical_variety` | gfan | dim, lineality, f-vector of trop V(I) |
| `simplicial_homology` | polymake | reduced integral homology incl. torsion |
| `graph_canonical_form` | nauty | canonical form of a vertex-coloured graph (isomorphism test) |
| `lean_check` | Lean | compile against Mathlib; axioms per theorem; flags `sorry` |
| `singular_run`, `m2_run`, `regina_run` | Singular, M2, Regina | raw scripts |
| `triangulation_invariants` | Regina | 3-/4-manifold triangulation (isomorphism signature): H1, H2, pi1, census names, intersection form; optional 3-sphere/ball/solid-torus recognition and prime decomposition |
| `census_lookup` | Regina | names in Regina's census databases |
| `hyperbolic_structure` | Regina (SnapPea) | solution type, volume, Dehn fillings |
| `turaev_viro` | Regina | exact Turaev-Viro invariants and their values at every root of unity |
| `link_invariants` | Regina | Jones, HOMFLY-PT, Alexander, complement of a knot/link diagram |
| `normal_surfaces` | Regina | vertex/fundamental normal surfaces and their topology |
| `pachner_walk` | Regina | reproducible random 2-3 (and 4-4) moves: scrambled triangulations of the same manifold |
| `simplify_triangulations` | Regina | batch simplification: repeated greedy `simplify()`, then exhaustive search at increasing height |
| `matroid_invariants` | Python | linear matroid of rational vectors: flats, Möbius invariant, characteristic and Poincaré polynomials, beta invariant, circuits; Tutte polynomial and bases (≤ 16 elements); chirotope (`oriented=true`) |
| `orlik_solomon` | Macaulay2 | Hilbert function of the Orlik–Solomon algebra from the circuits, checked against the Poincaré polynomial from the flats |
| `oriented_matroid` | Python | oriented matroid of a real vector configuration: chirotope, signed circuits, acyclic / totally cyclic, topes and the set of attainable Morse indices; canonical forms up to relabelling and up to reorientation (≤ 7 elements) |
| `kazhdan_lusztig` | Python | Kazhdan–Lusztig polynomial and Z-polynomial (Hilbert series of the intersection cohomology module) of a linear matroid, from the lattice of flats |
| `chow_ring` | Macaulay2 | Hilbert function of the Chow ring or (`augmented=true`) the augmented Chow ring from its presentation, checked against the Feichtner–Yuzvinsky basis count from the flats |
| `hyperplane_arrangement` | Python | central or affine real arrangement: characteristic polynomial, intersection poset, regions and bounded regions (Zaslavsky), Betti numbers of the complexified complement |
| `polytope_invariants` | polymake | polytope from points or inequalities: f-vector, simple/simplicial, h-vector, dual h-vector, volume, lattice points, Ehrhart polynomial |
| `hessenberg_betti` | Python | BB Betti numbers of (partial) regular semisimple Hessenberg varieties |
| `hessenberg_betti_gkm` | Macaulay2 | the same, independently, via GKM |
| `hessenberg_faces` | Python | face poset: counts by rank, cover invariant |
| `hessenberg_face_poset_canonical` | nauty | face poset up to isomorphism |
| `hessenberg_face_poset_homology` | polymake | homology of the face poset's order complex |

## Use

```sh
python3 -m venv .venv && .venv/bin/pip install -e ".[test]"
.venv/bin/mte versions
.venv/bin/mte call hessenberg_betti '{"kbar": [2, 2], "h": [2, 2]}'      # Gr(2,4)
.venv/bin/pytest                                                           # 76 tests, a few minutes
```

MCP server: `.venv/bin/mtengine-mcp` (stdio transport). For Claude Code, add to the `.mcp.json`
of the project that uses it:

```json
{ "mcpServers": { "mtengine": { "command": "engine/.venv/bin/mtengine-mcp" } } }
```

(with the path adjusted to where this repository is checked out). Backends that are not
installed report `MISSING` in `mte versions`; everything else still works.

Regina runs in its own process through `regina-python`, which ships with Regina
(its Python module is built for the system Python and does not import inside this venv).
Set `MTENGINE_REGINA_PYTHON` to use another command, e.g. a `python3` that can
`import regina`. On Ubuntu, install Regina from its apt repository:
<https://regina-normal.github.io/install/ubuntu.html>.

```sh
.venv/bin/mte call triangulation_invariants '{"isosig": "cPcbbbiht"}'    # figure-eight complement (m004)
.venv/bin/mte call link_invariants '{"code": "4 6 2", "format": "dt"}'    # trefoil
.venv/bin/mte call hyperplane_arrangement '{"normals": [[1,0],[0,1],[1,1]], "constants": [0,0,1]}'
.venv/bin/mte call polytope_invariants '{"points": [[0,0,0],[1,0,0],[0,1,0],[0,0,1]]}'
```

The Lean backend compiles in a Lake project with Mathlib. The **standard project** is pinned in
this package (`src/mtengine/lean_project/`: `lean-toolchain`, `lakefile.toml` and a
`lake-manifest.json` with the exact Mathlib commit, currently tag `v4.36.0-rc1` = `625d8914`), so
every installation compiles against the same Lean and Mathlib. `mte lean-init` builds it in
`$XDG_DATA_HOME/mtengine/lean` (default `~/.local/share/mtengine/lean`) and downloads the
prebuilt Mathlib (about 5 GB, a few minutes; `--no-cache` skips it). It needs `elan`.

```sh
.venv/bin/mte lean-init                    # once
.venv/bin/mte lean-status                  # which project lean_check uses, and whether it is ready
.venv/bin/mte call lean_check '{"source": "import Mathlib\nexample : (2 : ℚ) + 2 = 4 := by norm_num"}'
```

A project with its own library (e.g. matroid_toric's `formal/`, for `import Formal`) is used
instead when it is the first Lake project (a directory with `lean-toolchain` and a lakefile) of:

1. `$MTENGINE_LEAN_PROJECT`;
2. `../formal` next to this checkout (where it is when mtengine is matroid_toric's `engine/`);
3. the standard project.

A candidate that is not a Lake project, such as a variable naming a directory that does not exist
in this checkout, is skipped and listed by `lean_status`; a chosen project that is not built is
reported, not passed over. `lean_status` (`mte lean-status`), `mte versions` and the test
suite read the same answer, and `lean_check` refuses to run, saying what to do, when the project
is not ready. Its results are cached per Lean and Mathlib version and per content of the
project's own files, so editing a proof in `formal/` invalidates the results that used it; each
result names the project it was compiled in.

To move the pin to another Mathlib release: `mte lean-init --mathlib <tag> <dir>`, then copy
`lean-toolchain`, `lakefile.toml` and `lake-manifest.json` from `<dir>` into
`src/mtengine/lean_project/`.

## Reproducible toolchain

`Dockerfile` builds Ubuntu 24.04 with every backend at the versions tested here
(Macaulay2 1.22, gfan 0.6.2, polymake 4.11, Singular 4.3.2, nauty 2.8.8, Lean 4.36.0-rc1 +
Mathlib, Regina 7.4.1), plus Normaliz 3.10.2, without which Macaulay2's Polyhedra and the
packages built on it (Matroids, NormalToricVarieties, GKMVarieties, Tropical) do not load.
Normaliz is a system package, not a Python one: `pip install` cannot bring it, so a
non-Docker setup installs it with the other backends (`apt-get install normaliz`).

```sh
docker build -t mtengine .
docker run --rm mtengine .venv/bin/pytest -q                                  # Lean tests skip
docker run --rm -v /path/to/matroid_toric/formal:/work/formal mtengine .venv/bin/pytest -q
docker run -i --rm mtengine                                                   # MCP server, stdio
```

A Lake project mounted at `/work/formal` is picked up automatically (it is the sibling of the
checkout at `/work/engine`). `--build-arg WITH_MATHLIB=1` runs `mte lean-init` at build time
instead, adding about 5 GB of prebuilt Mathlib to the image. Test-built on 2026-11-09: the
suite passes in the image (51 passed, 2 Lean tests skipped), and the Lean tests pass with
matroid_toric's `formal/` mounted.

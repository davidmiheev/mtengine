# mtengine

One interface to the tools of the matroid_toric project: **Macaulay2, gfan, polymake, Singular,
nauty, Lean 4/Mathlib, Regina**, plus the project's own mathematics (regular semisimple and partial
Hessenberg varieties, GKM graphs, face posets). Split out of
[matroid_toric](https://github.com/davidmiheev/matroid_toric), which uses it as a git submodule at
`engine/`; the history of `engine/` is preserved here.

## Design

```
            Python API (mtengine.api)  ←  one source of truth: FUNCTIONS
              ↑                ↑                 ↑
         mte CLI         MCP server        your scripts / notebooks
                    (mtengine-mcp, stdio)
  ─────────────────────────────────────────────────────────────────
  core: process runner · result cache keyed by (backend, version, input) · provenance · job queue
  backends: macaulay2 · gfan · polymake · singular · nauty · lean · regina
  domain:   hessenberg (fixed points, BB Betti numbers, GKM graphs, faces) · posets
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
.venv/bin/pytest                                                           # 39 tests, ~30 s
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
```

The Lean backend compiles against a Lake project with Mathlib. By default it looks for
`../formal` next to this checkout, which is where it is inside matroid_toric. Elsewhere, set
`MTENGINE_LEAN_PROJECT` to the project directory.

## Reproducible toolchain

`Dockerfile` builds Ubuntu 24.04 with every backend at the versions tested here
(Macaulay2 1.22, gfan 0.6.2, polymake 4.11, Singular 4.3.2, nauty 2.8.8, Lean 4.36.0-rc1 +
Mathlib, Regina 7.4.1). Build from this repository: `docker build -t mtengine .`. To use the Lean backend,
mount a Lake project at `/work/formal` (e.g. matroid_toric's `formal/`). The Dockerfile has not
been test-built yet.

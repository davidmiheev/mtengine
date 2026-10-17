# mtengine

One interface to the tools of the matroid_toric project: **Macaulay2, gfan, polymake, Singular,
nauty, Lean 4/Mathlib**, plus the project's own mathematics (regular semisimple and partial
Hessenberg varieties, GKM graphs, face posets). Written to be split into its own repository.

## Design

```
            Python API (mtengine.api)  ←  one source of truth: FUNCTIONS
              ↑                ↑                 ↑
         mte CLI         MCP server        your scripts / notebooks
                    (mtengine-mcp, stdio)
  ─────────────────────────────────────────────────────────────────
  core: process runner · result cache keyed by (backend, version, input) · provenance · job queue
  backends: macaulay2 · gfan · polymake · singular · nauty · lean
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
| `singular_run`, `m2_run` | Singular, M2 | raw scripts |
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
.venv/bin/pytest                                                           # 25 tests, ~25 s
```

MCP (Claude Code picks up the repository's `.mcp.json`; for other clients point them at
`engine/.venv/bin/mtengine-mcp`, stdio transport).

The Lean backend uses the project in `../formal` (override with `MTENGINE_LEAN_PROJECT`).

## Reproducible toolchain

`Dockerfile` builds Ubuntu 24.04 with every backend at the versions tested here
(Macaulay2 1.22, gfan 0.6.2, polymake 4.11, Singular 4.3.2, nauty 2.8.8, Lean 4.36.0-rc1 +
Mathlib). Build from the repository root: `docker build -f engine/Dockerfile .`

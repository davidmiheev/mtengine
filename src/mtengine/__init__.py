"""mtengine: an engine for computational experiments in topology and geometry.

One interface to Macaulay2, gfan, polymake, Singular, nauty, Lean and Regina; it began as the
engine of the matroid_toric project.

Layers:
  core      -- process runner, content-addressed result cache with provenance, job queue
  backends  -- thin adapters: macaulay2, gfan, polymake, singular, nauty, lean, regina
  domain    -- mathematics built on the backends (Hessenberg varieties, GKM graphs, posets)
  api       -- the public functions; the CLI (`mte`) and the MCP server expose exactly these
"""
__version__ = "0.1.0"
